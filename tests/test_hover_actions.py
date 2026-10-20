"""Functional hover-action regression; no browser or visual automation."""
import ast
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from unittest.mock import patch

from test_audio_safety import mcc


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('MCC_TEST_SOURCE', str(ROOT / 'Music Collection Cleaner v0.05.53.pyw')))
NODE = shutil.which('node')


def map_html():
    module = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
    function = next(node for node in module.body
                    if isinstance(node, ast.FunctionDef) and node.name == '_webview_release_map_html')
    return next(node.value.value for node in function.body
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                and any(isinstance(target, ast.Name) and target.id == 'html' for target in node.targets))


class Buttons(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.buttons = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'button':
            self.current = dict(attrs, text='')
            self.buttons.append(self.current)

    def handle_data(self, data):
        if self.current is not None:
            self.current['text'] += data

    def handle_endtag(self, tag):
        if tag == 'button':
            self.current = None


@unittest.skipUnless(NODE, 'Node is required for functional embedded-JavaScript checks')
class HoverActions(unittest.TestCase):
    def run_js(self, script, data):
        result = subprocess.run([NODE, '-e', script], input=json.dumps(data),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_copy_and_version_status_is_preserved_without_generic_needed_label(self):
        html=map_html()
        code=html[html.index('function exclusionStatus('):html.index('function closeDetails(')]
        cases=[
            ({'unique':False,'audioMatchEditions':0,'unverifiedEditions':1},'Also listed on 1 edition (audio unverified)'),
            ({'unique':False,'audioMatchEditions':2,'unverifiedEditions':1},'Same audio on 2 editions; Also listed on 1 edition (audio unverified)'),
            ({'unique':True,'audioMatchEditions':0,'unverifiedEditions':0},'Unique to this release'),
            ({'unique':False,'coveredBy':['Retained Deluxe']},'Also on: Retained Deluxe'),
            ({'unique':True,'coveredBy':['Retained Deluxe']},'Also on: Retained Deluxe'),
            ({'unique':False,'excluded':True,'isLive':True},'Excluded: Live'),
            ({'unique':True,'excluded':True,'isLive':True},'Excluded: Live'),
            ({'unique':True,'manualSkip':True,'groupId':5},'Ignored recording everywhere'),
        ]
        statuses=self.run_js(r'''
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
const status=new Function(input.code+'\nreturn trackStatus;')();
process.stdout.write(JSON.stringify(input.tracks.map(t=>status(t,{kind:'retained'}))));
''',{'code':code,'tracks':[track for track,_ in cases]})
        for (track,expected),actual in zip(cases,statuses):
            with self.subTest(track=track):
                self.assertEqual(actual,expected)

    def test_only_other_retained_coverage_cancels_retention_highlights(self):
        a=[mcc.Track(1,Path('A/common.flac'),1,title='Common',artist='Artist',duration=120,group_id=0),
           mcc.Track(1,Path('A/needed.flac'),2,title='Needed',artist='Artist',duration=120,group_id=1)]
        b=[mcc.Track(2,Path('B/common.flac'),1,title='Common',artist='Artist',duration=120,group_id=0),
           mcc.Track(2,Path('B/needed.flac'),2,title='Needed',artist='Artist',duration=120,group_id=2)]
        releases=[mcc.Release(1,'existing',Path('Album A'),'Album A',tracks=a),
                  mcc.Release(2,'recycle',Path('Album B'),'Album B',tracks=b)]
        snapshots=mcc.build_decision_snapshot(releases,a+b,{1,2},
            [mcc.ReleaseDecision(1,'KEEP','needed'),mcc.ReleaseDecision(2,'ADD','needed')])
        with patch.object(mcc,'_load_pattern_categories',return_value={}), \
             patch.object(mcc,'_load_app_settings',return_value={}), \
             patch.object(mcc,'_assign_release_map_display_groups'):
            state=mcc._release_map_state_for_ui(snapshots,None,set(),set(),set(),True,False,False,False)
        for node in state['nodes']:
            self.assertEqual(node['uniqueCount'],1)
            self.assertFalse(node['tracks'][0]['unique'])
            self.assertTrue(node['tracks'][0]['coveredBy'])
            # Each distinct recording is a reason its release is retained.
            # A similar title is informative, not verified coverage.
            self.assertTrue(node['tracks'][1]['unique'])
            self.assertEqual(node['tracks'][1]['unverifiedEditions'],1)

        # Cached snapshot annotations cannot highlight excluded/covered rows.
        for snapshot in snapshots:
            for row in snapshot['tracklist']:
                row['unique_to_release']=True
            snapshot['tracklist'][1]['excluded']=True
        with patch.object(mcc,'_load_pattern_categories',return_value={}), \
             patch.object(mcc,'_load_app_settings',return_value={}), \
             patch.object(mcc,'_assign_release_map_display_groups'):
            state=mcc._release_map_state_for_ui(snapshots,None,set(),set(),set(),True,False,False,False)
        self.assertTrue(all(node['uniqueCount']==0 for node in state['nodes']))
        self.assertFalse(any(t['unique'] for node in state['nodes'] for t in node['tracks']))

    def test_retained_carriers_change_highlights_but_discarded_copies_do_not(self):
        a=[mcc.Track(1,Path('A/shared.flac'),1,title='Shared',artist='Artist',duration=120,group_id=0),
           mcc.Track(1,Path('A/essential.flac'),2,title='Essential',artist='Artist',duration=120,group_id=1)]
        b=[mcc.Track(2,Path('B/shared.flac'),1,title='Shared',artist='Artist',duration=120,group_id=0),
           mcc.Track(2,Path('B/bonus.flac'),2,title='Bonus',artist='Artist',duration=120,group_id=2)]
        c=[mcc.Track(3,Path('C/essential.flac'),1,title='Essential',artist='Artist',duration=120,group_id=1)]
        releases=[mcc.Release(rid,'recycle',Path(name),name,tracks=tracks)
                  for rid,name,tracks in [(1,'A',a),(2,'B',b),(3,'C',c)]]
        for retained,expected in [({1,2},['Essential']),({1},['Shared','Essential'])]:
            with self.subTest(retained=retained):
                snapshots=mcc.build_decision_snapshot(releases,a+b+c,retained,
                    [mcc.ReleaseDecision(r.rid,'ADD' if r.rid in retained else 'SKIP','Plan') for r in releases])
                nodes={n['id']:n for n in self.ui_state(snapshots)['nodes']}
                rows=self.render_track_rows(list(nodes.values()))
                for node,rendered in zip(nodes.values(),rows):
                    titles=(expected if node['id']==1 else ['Bonus'] if node['id']==2 and 2 in retained else [])
                    self.assert_highlighted_rows(node,rendered,titles)
                self.assertEqual(nodes[1]['tracks'][1]['audioMatchEditions'],1)
                self.assertFalse(nodes[1]['tracks'][1]['isGem'])

    def ui_state(self,snapshots):
        with patch.object(mcc,'_load_pattern_categories',return_value={}), \
             patch.object(mcc,'_load_app_settings',return_value={}), \
             patch.object(mcc,'_assign_release_map_display_groups'):
            return mcc._release_map_state_for_ui(snapshots,None,set(),set(),set(),True,False,False,False)

    def render_track_rows(self,nodes):
        html=map_html()
        code=html[html.index('  let tracks="";',html.index('function openDetails(')):
                  html.index('  let ignoreRelease="";',html.index('function openDetails('))]
        status=html[html.index('function exclusionStatus('):html.index('function closeDetails(')]
        return self.run_js(r'''
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
const status=new Function(input.status+'\nreturn trackStatus;')();
const render=new Function('n','state','activeTrack','esc','versionsForTrack','remixesForTrack','liveForTrack','trackStatus',input.code+'\nreturn tracks;');
const esc=value=>String(value).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
process.stdout.write(JSON.stringify(input.nodes.map(n=>render(n,{editable:false},null,esc,()=>[],()=>[],()=>[],status))));
''',{'code':code,'status':status,'nodes':nodes})

    def assert_highlighted_rows(self,node,rows,expected_titles):
        self.assertEqual([t['title'] for t in node['tracks'] if t['unique']],expected_titles)
        self.assertEqual(node['uniqueCount'],len(expected_titles))
        classes=re.findall(r'<div class="(track[^"]*)"',rows)
        self.assertEqual(len(classes),len(node['tracks']))
        highlighted=[t['title'] for t,css in zip(node['tracks'],classes) if 'unique' in css.split()]
        self.assertEqual(highlighted,expected_titles)
        self.assertNotIn('Needed recording',rows)

    def test_actual_pablo_highlights_exactly_the_15_retention_reason_tracks(self):
        fixture=json.loads((ROOT/'tests/fixtures/pablo_retention_highlights.json').read_text())
        state=self.ui_state(fixture['snapshots'])
        nodes={n['id']:n for n in state['nodes']}
        target=nodes[64]
        expected=['Ultralight Beam','Father Stretch My Hands Pt. 1','Pt. 2','Famous',
                  'Feedback','Highlights','Freestyle 4','Waves','FML','Real Friends',
                  'Wolves','30 Hours','No More Parties In LA','Facts (Charlie Heat Version)','Fade']
        rows=self.render_track_rows([target,nodes[65],nodes[16]])
        self.assert_highlighted_rows(target,rows[0],expected)
        self.assert_highlighted_rows(nodes[65],rows[1],[t['title'] for t in fixture['snapshots'][2]['tracklist'] if t['unique_to_release']])
        self.assert_highlighted_rows(nodes[16],rows[2],[])
        covered=[t for t in target['tracks'] if t['title'] not in expected]
        self.assertEqual([t['title'] for t in covered],['Low Lights','I Love Kanye',"Frank's Track",'Siiiiiiiiilver Surffffeeeeer Intermission'])
        self.assertTrue(all(t['coveredBy'] and not t['unique'] for t in covered))
        self.assertTrue(any(t['unique'] and t['audioMatchEditions'] for t in target['tracks']))
        self.assertIn('Same audio on',rows[0])
        self.assertIn('Also listed on',rows[0])
        self.assertIn('Also on:',rows[0])
        html=map_html()
        code=html[html.index('function uniqueAddedTitles('):html.index('function changedNodes(')]
        result=self.run_js(r'''
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
const evaluate=new Function('n','replacementMap',input.code+'\nreturn {titles:uniqueAddedTitles(n),reason:changeReason(n,"added")};');
process.stdout.write(JSON.stringify(evaluate(input.node,()=>({}))));
''',{'code':code,'node':target})
        self.assertEqual(result['titles'],expected)
        self.assertEqual(result['reason'],'Retained for: Ultralight Beam; Father Stretch My Hands Pt. 1; Pt. 2; +12 more')

    def test_actual_bully_highlights_follow_logged_retention_reasons(self):
        fixture=json.loads((ROOT/'tests/fixtures/bully_song_presence.json').read_text())
        state=self.ui_state(fixture['snapshots'])
        standard=next(n for n in state['nodes'] if n['id']==100)
        deluxe=next(n for n in state['nodes'] if n['id']==102)
        self.assertEqual(standard['uniqueCount'],18)
        self.assertEqual(deluxe['uniqueCount'],20)
        for index in range(18):
            self.assertTrue(standard['tracks'][index]['unique'])
            self.assertTrue(deluxe['tracks'][index]['unique'])
            self.assertEqual(standard['tracks'][index]['groupId'],fixture['snapshots'][1]['tracklist'][index]['group_id'])
        # The logged acoustic groups remain distinct. Display metadata must
        # not silently override the actual reasons for retaining a release.
        self.assertTrue(deluxe['tracks'][19]['unique'])
        nodes=[standard,deluxe,next(n for n in state['nodes'] if n['id']==103)]
        rendered=self.render_track_rows(nodes)
        for node,rows in zip(nodes,rendered):
            snapshot=next(s for s in fixture['snapshots'] if s['release_id']==node['id'])
            expected=[t['title'] for t in snapshot['tracklist'] if t['unique_to_release']]
            self.assert_highlighted_rows(node,rows,expected)
        self.assertIn('Also listed on',rendered[0])
        self.assertIn('Also listed on',rendered[1])

    def test_song_presence_respects_artist_family_and_does_not_merge_audio(self):
        def row(title,artist,gid,**extra):
            return dict(title=title,artist=artist,group_id=gid,coverage_group_id=gid,
                        included=True,excluded=False,unique_to_release=True,**extra)
        snapshots=[dict(release_id=1,name='A',action='KEEP',tracklist=[
            row('Shared','Kanye West',1),row('Alone','Kanye West',2),
            row('Cover','Artist A',3),row('Dance (Club Remix)','Artist A',4,is_remix=True),
            row('Alternate title','Artist A',7)]),
            dict(release_id=2,name='B',action='SKIP',tracklist=[
            row('Shared (feat. Guest)','Ye',5,duration_seconds=180),
            row('Cover','Artist B',6),row('Dance','Artist A',8),
            row('Original title','Artist A',7)])]
        state=self.ui_state(snapshots);a=next(n for n in state['nodes'] if n['id']==1)
        self.assertEqual([t['unique'] for t in a['tracks']],[True,True,True,True,True])
        self.assertEqual([t['groupId'] for t in a['tracks']],[1,2,3,4,7])
        self.assertEqual([t['unverifiedEditions'] for t in a['tracks']],[1,0,0,0,0])
        self.assertEqual([t['audioMatchEditions'] for t in a['tracks']],[0,0,0,0,1])
        discarded=next(n for n in state['nodes'] if n['id']==2)
        self.assertFalse(any(t['unique'] for t in discarded['tracks']))

    def test_unverified_listing_cannot_keep_a_unique_gem_badge(self):
        snapshots=[dict(release_id=1,name='A',action='KEEP',tracklist=[dict(
            title='Song',artist='Artist',group_id=1,included=True,unique_to_release=True)]),
            dict(release_id=2,name='B',action='SKIP',tracklist=[dict(
            title='Song',artist='Artist',group_id=-1,included=False,excluded=True)])]
        state=self.ui_state(snapshots);a=next(n for n in state['nodes'] if n['id']==1)
        self.assertTrue(a['tracks'][0]['unique'])
        self.assertFalse(a['tracks'][0]['isGem'])
        self.assertFalse(a['isGem'])

    def test_ignore_restore_delta_keeps_rows_count_changes_and_gems_in_sync(self):
        tracks=[mcc.Track(1,Path('A/song.flac'),1,title='Song',artist='Artist',duration=120,group_id=0),
                mcc.Track(2,Path('B/song.flac'),1,title='Song',artist='Artist',duration=120,group_id=0),
                mcc.Track(1,Path('A/rare.flac'),2,title='Rare',artist='Artist',duration=120,group_id=1)]
        releases=[mcc.Release(1,'recycle',Path('A'),'A',tracks=[tracks[0],tracks[2]]),
                  mcc.Release(2,'recycle',Path('B'),'B',tracks=[tracks[1]])]
        snapshots=mcc.build_decision_snapshot(releases,tracks,{1},
            [mcc.ReleaseDecision(1,'ADD','Plan'),mcc.ReleaseDecision(2,'SKIP','Duplicate')])
        session=dict(snapshots=snapshots,releases=releases,tracks=tracks,groups={0:[0,1],1:[2]},selected={1},allow_apply=True)
        tree=ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        launch=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='launch_webview_release_map')
        bridge_class=next(n for n in launch.body if isinstance(n,ast.ClassDef) and n.name=='ReleaseMapBridge')
        namespace=dict(vars(mcc),session=session)
        # Run the actual bridge, with persistence replaced by in-memory rules.
        def ignore(track,all_tracks):
            for item in all_tracks:
                if item.group_id==track.group_id:item.manual_skip_rule='fixture:'+str(track.group_id)
        def restore(rule,all_tracks):
            for item in all_tracks:
                if item.manual_skip_rule==rule:item.manual_skip_rule=''
        namespace.update(add_persistent_track_skip=ignore,remove_persistent_track_skip=restore)
        exec(compile(ast.Module(body=[bridge_class],type_ignores=[]),str(SOURCE),'exec'),namespace)
        payloads=[]
        with patch.object(mcc,'_load_pattern_categories',return_value={}), \
             patch.object(mcc,'_load_app_settings',return_value={}), \
             patch.object(mcc,'_assign_release_map_display_groups'):
            bridge=namespace['ReleaseMapBridge']()
            initial=json.loads(json.dumps(bridge._ui_state))
            for index,count,gem in [(0,1,True),(2,0,False),(0,1,False),(2,2,True)]:
                payload=json.loads(bridge.toggleTrack(index));payloads.append(payload)
                nodes={n['id']:n for n in bridge._ui_state['nodes']}
                self.assertEqual(nodes[1]['uniqueCount'],count)
                self.assertEqual(nodes[1]['isGem'],gem)
                self.assertEqual(nodes[1]['gemTitles'],['Rare'] if gem else [])
                self.assertFalse(any(t['unique'] or t['isGem'] for t in nodes[2]['tracks']))
                self.assertEqual({t['index'] for t in payload['tracks']},{0,1} if index==0 else {2})
                for n in nodes.values():
                    for t in n['tracks']:
                        if t['manualSkip']:self.assertFalse(t['unique'] or t['isGem'])
                rows=self.render_track_rows([nodes[1]])[0]
                self.assert_highlighted_rows(nodes[1],rows,[t['title'] for t in nodes[1]['tracks'] if t['unique']])
                self.assertEqual(rows.count('class="trackGem"'),int(gem))
        html=map_html()
        policy=html[html.index('function uniqueAddedTitles('):html.index('function changedNodes(')]
        toggle=html[html.index('function receiveTrackToggle('):html.index('function receiveReleaseToggle(')]
        status=html[html.index('function exclusionStatus('):html.index('function closeDetails(')]
        results=self.run_js(r'''
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
const state=input.state,selectedId=1,current=state.nodes.find(n=>n.id===selectedId);
let replacementCache=null;
const essential={textContent:' · 2 essential',hidden:false};
const reason={textContent:''},releaseRow={dataset:{},querySelector:()=>reason,setAttribute:()=>{},getAttribute:()=>''};
const rowEls=new Map([['1',releaseRow]]);
const rows=current.tracks.map(t=>{
  const classes=new Set(['track','unique']);
  const row={dataset:{index:t.index},hasGem:t.isGem,status:{},button:{setAttribute:()=>{}},
    classList:{toggle:(c,on)=>on?classes.add(c):classes.delete(c)},classes};
  row.querySelector=s=>s==='.status'?row.status:s==='.ignoreTrack'?row.button:
    s==='.trackGem'?(row.hasGem?{remove:()=>row.hasGem=false}:null):
    s==='.versionsCell'?{insertAdjacentHTML:()=>row.hasGem=true}:null;
  return row;
});
const document={getElementById:id=>id==='essentialCount'?essential:null,querySelectorAll:()=>rows};
const getNode=id=>state.nodes.find(n=>Number(n.id)===Number(id));
const applyRootPatch=()=>{},receiveState=()=>{throw Error('Unexpected full-state fallback')};
const changeKind=()=> 'added',replacementMap=()=>({}),paintReanalyzeHighlight=()=>{};
const trackStatus=new Function(input.status+'\nreturn trackStatus;')();
eval(input.policy+'\n'+input.toggle);
const results=[];
for(const p of input.payloads){
  receiveTrackToggle(JSON.stringify(p));
  results.push({count:current.uniqueCount,hidden:essential.hidden,label:essential.textContent,
    titles:uniqueAddedTitles(current),reason:reason.textContent,gem:current.isGem,
    rows:rows.map(r=>({index:r.dataset.index,highlight:r.classes.has('unique'),gem:r.hasGem}))});
}
process.stdout.write(JSON.stringify(results));
''',{'state':initial,'payloads':payloads,'policy':policy,'toggle':toggle,'status':status})
        for result,count,titles,gem in zip(results,[1,0,1,2],[['Rare'],[],['Song'],['Song','Rare']],[True,False,False,True]):
            self.assertEqual(result['count'],count)
            self.assertEqual(result['hidden'],count==0)
            self.assertEqual(result['label'],' · '+str(count)+' essential')
            self.assertEqual(result['titles'],titles)
            self.assertEqual(result['gem'],gem)
            self.assertEqual([r['highlight'] for r in result['rows']],['Song' in titles,'Rare' in titles])
            self.assertEqual([r['gem'] for r in result['rows']],[False,gem])
            if titles:self.assertEqual(result['reason'],'Retained for: '+'; '.join(titles))
            else:self.assertIn('Re-Analyze',result['reason'])

    def test_one_ignore_action_preserves_saved_categories_and_restore(self):
        html = map_html()
        # Execute the real action-producing code without a DOM or renderer.
        start = html.index('    let action="";')
        code = html[start:html.index('    const statusText=trackStatus(t,n);', start)]
        cases = [
            ('normal', {}, True, ['remix', 'live'], 'Ignore'),
            ('saved remix', {'patternKind': 'remix'}, True, ['live'], 'Ignore'),
            ('saved live', {'patternKind': 'live'}, True, ['remix'], 'Ignore'),
            ('saved skip', {'patternKind': 'skip', 'excluded': True}, True, ['remix', 'live'], None),
            ('ignored', {'manualSkip': True, 'excluded': True}, True, ['remix', 'live'], 'Restore'),
            ('pending ignore', {'manualSkip': True, 'pendingIgnore': True}, True, ['remix', 'live'], 'Restore'),
            ('pending restore', {'excluded': True, 'pendingRestore': True}, True, ['remix', 'live'], 'Ignore'),
            ('option excluded', {'excluded': True}, True, ['remix', 'live'], None),
            ('ungrouped', {'groupId': -1}, True, ['remix', 'live'], 'Ignore'),
            ('read only', {'patternKind': 'skip'}, False, [], None),
        ]
        inputs = [{'track': {'index': 7, 'groupId': 42, **patch}, 'editable': editable}
                  for _, patch, editable, _, _ in cases]
        outputs = self.run_js(r'''
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
const render=new Function('t','state','esc','versionsForTrack','remixesForTrack','liveForTrack',
  input.code+'\nreturn {actions,badge};');
const esc=value=>String(value).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
process.stdout.write(JSON.stringify(input.cases.map(item=>
  render(item.track,{editable:item.editable},esc,()=>[],()=>[],()=>[]))));
''', {'code': code, 'cases': inputs})
        for (name, patch, _, expected_kinds, expected_label), rendered in zip(cases, outputs):
            with self.subTest(state=name):
                buttons = Buttons(rendered['actions']).buttons
                self.assertEqual([b.get('data-kind') for b in buttons if b.get('class') == 'patternMark'],
                                 expected_kinds)
                ignore = [b for b in buttons if b.get('class') == 'ignoreTrack']
                self.assertEqual(len(ignore), int(expected_label is not None))
                if expected_label is not None:
                    self.assertEqual(ignore[0]['text'], expected_label)
                    scope = 'this track' if patch.get('groupId') == -1 else 'this recording everywhere'
                    self.assertEqual(ignore[0]['aria-label'], expected_label + ' ' + scope)
                badges = Buttons(rendered['badge']).buttons
                self.assertEqual(len(badges), int(bool(patch.get('patternKind'))))
                if badges:
                    self.assertEqual(badges[0]['title'], 'Move to Personal Picks')

    def test_native_buttons_route_to_existing_recording_and_pattern_handlers(self):
        html = map_html()
        start = html.index('  inner.querySelectorAll(".patternMark")')
        code = html[start:html.index('  inner.querySelectorAll(".versionsTrack")', start)]
        calls = self.run_js(r'''
const code=JSON.parse(require('fs').readFileSync(0,'utf8')).code;
const calls=[],buttons={
  '.patternMark':[{dataset:{track:'7',kind:'remix'}},{dataset:{track:'7',kind:'live'}}],
  '.patternBadge':[{dataset:{track:'7'}}],
  '.ignoreTrack':[{dataset:{track:'7'}}]
};
const inner={querySelectorAll:selector=>buttons[selector]};
const bridge={markTrackPattern:(index,kind)=>calls.push(['pattern',index,kind]),
  toggleTrack:index=>calls.push(['recording',index])};
new Function('inner','bridge','receivePatternClassification','receiveTrackToggle',code)(inner,bridge,()=>{},()=>{});
let stopped=0;
Object.values(buttons).flat().forEach(button=>button.onclick({stopPropagation:()=>stopped++}));
process.stdout.write(JSON.stringify({calls,stopped}));
''', {'code': code})
        self.assertEqual(calls, {'calls': [['pattern', 7, 'remix'], ['pattern', 7, 'live'],
                                          ['pattern', 7, 'keep'], ['recording', 7]], 'stopped': 4})


if __name__ == '__main__':
    unittest.main()
