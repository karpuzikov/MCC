import ast
import json
import runpy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch


from test_audio_safety import mcc

source = Path(mcc.__file__)
ns = runpy.run_path(str(source))['analyze'].__globals__
tree = ast.parse(source.read_text(encoding='utf-8-sig'))
bridge_class = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.ClassDef) and node.name == 'MainBridge')
exec(compile(ast.Module(body=[bridge_class], type_ignores=[]), str(source), 'exec'), ns)


class InlineThread:
    def __init__(self, target, args, daemon):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


class PostScanReviewTests(unittest.TestCase):
    def test_review_order(self):
        for choice in ('skip', 'later', 'cancel', 'already deferred'):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                releases = []
                titles = ('Song (Callout Hook)', 'Other Song (Callout Hook)')
                for index, title in enumerate(titles):
                    path = root / str(index) / (title + '.flac')
                    path.parent.mkdir()
                    path.touch()
                    track = ns['Track'](index, path, 0, title=title, artist='Artist', duration=60,
                                        fingerprint=(index + 1,) * 100, group_id=index)
                    releases.append(ns['Release'](index, 'recycle', path.parent, title, tracks=[track]))
                tracks = [release.tracks[0] for release in releases]
                events = []

                class Cache:
                    dynamic_dirty = False
                    def __init__(self, full_rescan=False):
                        assert full_rescan is True

                    def save(self):
                        events.append('cache')

                    def check_sources(self):
                        events.append('check sources')

                def prepare(*args, scan_cache=None):
                    events.append('prepare')
                    return releases, tracks

                def analyze(*args, optimize_plan=True, scan_cache=None, **kwargs):
                    assert optimize_plan is False
                    events.append('acoustic')
                    return releases, tracks, {0: [0], 1: [1]}, set(), [], []

                def optimize(releases, groups, *, blocked_release_ids, **kwargs):
                    assert blocked_release_ids == {1}
                    events.append('optimize')
                    return {rel.rid for rel in releases if rel.groups and rel.rid not in blocked_release_ids}

                reclassify = ns['_reclassify_without_acoustic_work']

                def from_evidence(*args, restrict_to_scanned, **kwargs):
                    assert restrict_to_scanned is True
                    if 'restrict_to_scanned' in reclassify.__code__.co_varnames:
                        kwargs['restrict_to_scanned'] = restrict_to_scanned
                    return reclassify(*args, **kwargs)

                pending_rows = ns['collect_track_patterns'](tracks[:1]) if choice == 'already deferred' else []
                with patch.dict(ns, {
                    '_load_app_settings': lambda: {},
                    '_load_decision_snapshot': lambda: [],
                    '_load_pending_pattern_reviews': lambda: pending_rows,
                    '_load_pattern_categories': lambda: {},
                    '_save_pattern_categories': lambda choices: events.append('persist choice'),
                    '_save_pending_pattern_reviews': lambda rows: events.append('persist pending'),
                    '_save_decision_snapshot': lambda rows: None,
                    '_load_manual_track_skip_rules': lambda: [],
                    '_load_manual_ignored_release_paths': lambda: {ns['_manual_album_group_path_key'](releases[1].path)},
                    'prepare_analysis': prepare,
                    'analyze_prepared': analyze,
                    'optimize_collection': optimize,
                    '_reclassify_without_acoustic_work': from_evidence,
                    'ScanCache': Cache,
                }), patch.object(ns['threading'], 'Thread', InlineThread):
                    bridge = ns['MainBridge']()
                    bridge._emit_state = lambda *args, **kwargs: None
                    errors = []

                    def event(payload):
                        if payload['type'] == 'error':
                            errors.append(payload['message'])
                        else:
                            assert payload['type'] == 'patternReview'
                            events.append('review')
                            assert payload['patterns'][0]['count'] == 1

                    bridge._event = event
                    bridge._launch_release_map = lambda: events.append('map')
                    bridge.running = True
                    cache_arg = {'full_rescan': True} if 'full_rescan' in bridge._preflight_worker.__code__.co_varnames else {}
                    bridge._preflight_worker(None, root, False, False, False, 2, **cache_arg)
                    if choice == 'already deferred':
                        assert events == ['prepare', 'acoustic', 'optimize', 'cache', 'map'], (events, errors)
                        assert bridge.pending_pattern_reviews == pending_rows
                        assert json.loads(bridge.getPersonalPicks())['pending'] == pending_rows
                        assert not bridge.review_pending and not bridge.running and not errors
                        continue
                    assert events == ['prepare', 'acoustic', 'cache', 'review'], (events, errors)
                    assert bridge.review_pending and not bridge.running
                    key = bridge._review_visible_rows[0]['key']
                    if choice == 'skip':
                        bridge.submitPatternReview(json.dumps({key: 'skip'}))
                        assert tracks[0].exclude_from_coverage and tracks[0].group_id == 0
                        assert bridge._live_release_map_session['selected'] == set()
                        assert events[4:] == ['persist choice', 'persist pending', 'optimize', 'check sources', 'map']
                    elif choice == 'later':
                        bridge.deferPatternReview('{}')
                        assert bridge._live_release_map_session['selected'] == {0}
                        assert bridge.pending_pattern_reviews[0]['key'] == key
                        assert events[4:] == ['persist pending', 'optimize', 'check sources', 'map']
                    else:
                        bridge.cancelReview()
                        assert bridge._live_release_map_session is None
                        assert bridge._pending_analysis is None
                        assert events[4:] == []
                    assert not bridge.review_pending and not bridge.running and not errors
