"""Functional hover-action regression; no browser or visual automation."""
import ast
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from test_audio_safety import mcc


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('MCC_TEST_SOURCE', str(ROOT / 'Music Collection Cleaner v0.05.47.pyw')))
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
                                capture_output=True, text=True, check=True)
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

    def test_shared_song_is_not_highlighted_even_with_distinct_audio_groups(self):
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
            self.assertEqual(node['uniqueCount'],0)
            self.assertFalse(node['tracks'][0]['unique'])
            self.assertTrue(node['tracks'][0]['coveredBy'])
            # Song presence controls the highlight; distinct audio groups
            # remain separate optimizer obligations and version details.
            self.assertFalse(node['tracks'][1]['unique'])
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

    def ui_state(self,snapshots):
        with patch.object(mcc,'_load_pattern_categories',return_value={}), \
             patch.object(mcc,'_load_app_settings',return_value={}), \
             patch.object(mcc,'_assign_release_map_display_groups'):
            return mcc._release_map_state_for_ui(snapshots,None,set(),set(),set(),True,False,False,False)

    def test_actual_bully_album_rows_are_not_all_highlighted(self):
        fixture=json.loads((ROOT/'tests/fixtures/bully_song_presence.json').read_text())
        state=self.ui_state(fixture['snapshots'])
        standard=next(n for n in state['nodes'] if n['id']==100)
        deluxe=next(n for n in state['nodes'] if n['id']==102)
        self.assertEqual([t['title'] for t in standard['tracks'] if t['unique']],[])
        self.assertEqual([t['title'] for t in deluxe['tracks'] if t['unique']],['OK (feat. Don Toliver)'])
        self.assertEqual(standard['uniqueCount'],0)
        self.assertEqual(deluxe['uniqueCount'],1)
        for index in range(18):
            self.assertFalse(standard['tracks'][index]['unique'])
            self.assertFalse(deluxe['tracks'][index]['unique'])
            self.assertEqual(standard['tracks'][index]['groupId'],fixture['snapshots'][1]['tracklist'][index]['group_id'])
        # Mission Control is also on its discarded single. Physical song
        # presence still rules out a collection-wide uniqueness highlight.
        self.assertFalse(deluxe['tracks'][19]['unique'])
        html=map_html()
        code=html[html.index('  let tracks="";',html.index('function openDetails(')):
                  html.index('  let ignoreRelease="";',html.index('function openDetails('))]
        status=html[html.index('function exclusionStatus('):html.index('function closeDetails(')]
        rendered=self.run_js(r'''
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
const status=new Function(input.status+'\nreturn trackStatus;')();
const render=new Function('n','state','activeTrack','esc','versionsForTrack','remixesForTrack','liveForTrack','trackStatus',input.code+'\nreturn tracks;');
const esc=value=>String(value).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
process.stdout.write(JSON.stringify(input.nodes.map(n=>render(n,{editable:false},null,esc,()=>[],()=>[],()=>[],status))));
''',{'code':code,'status':status,'nodes':[standard,deluxe]})
        for rows,expected in zip(rendered,[0,1]):
            # Execute the real row HTML producer: the corrected flag must
            # actually remove the amber CSS class, not merely change a label.
            import re
            classes=re.findall(r'<div class="(track[^"]*)"',rows)
            self.assertEqual(sum('unique' in value.split() for value in classes),expected)
            self.assertNotIn('Needed recording',rows)
            self.assertIn('Also listed on',rows)

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
        self.assertEqual([t['unique'] for t in a['tracks']],[False,True,True,True,False])
        self.assertEqual([t['groupId'] for t in a['tracks']],[1,2,3,4,7])

    def test_unverified_listing_cannot_keep_a_unique_gem_badge(self):
        snapshots=[dict(release_id=1,name='A',action='KEEP',tracklist=[dict(
            title='Song',artist='Artist',group_id=1,included=True,unique_to_release=True)]),
            dict(release_id=2,name='B',action='SKIP',tracklist=[dict(
            title='Song',artist='Artist',group_id=-1,included=False,excluded=True)])]
        state=self.ui_state(snapshots);a=next(n for n in state['nodes'] if n['id']==1)
        self.assertFalse(a['tracks'][0]['unique'])
        self.assertFalse(a['tracks'][0]['isGem'])
        self.assertFalse(a['isGem'])

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
