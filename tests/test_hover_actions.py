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
SOURCE = Path(os.environ.get('MCC_TEST_SOURCE', str(ROOT / 'Music Collection Cleaner v0.05.46.pyw')))
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

    def test_highlight_status_explains_retention_not_title_based_duplicates(self):
        html=map_html()
        code=html[html.index('function exclusionStatus('):html.index('function closeDetails(')]
        cases=[
            ({'unique':True,'audioMatchEditions':0,'unverifiedEditions':1},'Needed recording'),
            ({'unique':True,'audioMatchEditions':2,'unverifiedEditions':1},'Needed recording'),
            ({'unique':True,'audioMatchEditions':0,'unverifiedEditions':0},'Needed recording'),
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

    def test_highlights_follow_retention_coverage_not_similar_titles(self):
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
            # Same title/length, distinct acoustic groups: it still justifies
            # retaining this release until an audio match is established.
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
