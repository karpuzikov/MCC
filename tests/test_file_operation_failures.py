"""Copy and Move must report failures and never lose music."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_audio_safety import mcc

OPTIONS = {"format": "FLAC", "enable_encoding": False, "enable_checker": False, "enable_splitting": False}


class FileOperationFailures(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='mcc-file-operations-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.old_root, self.new_root = root / 'OLD', root / 'NEW'
        self.destination = root / 'UPDATED'
        self.sources, self.releases, self.decisions = [], [], []
        for index, (root_kind, scan_root, action) in enumerate(
                (('existing', self.old_root, 'KEEP'), ('recycle', self.new_root, 'ADD'))):
            folder = scan_root / 'Albums' / f'Edition {index}'
            folder.mkdir(parents=True)
            (folder / '01 track.flac').write_bytes(b'audio %d' % index)
            self.sources.append(folder)
            self.releases.append(mcc.Release(9100 + index, root_kind, folder, f'Edition {index}', scan_root=scan_root))
            self.decisions.append(mcc.ReleaseDecision(9100 + index, action, 'Retained'))
        for name in ('DATA', 'UNDO', 'REPORT', 'HISTORY', 'ARTWORK_UNDO'):
            target = root / 'data' / name
            patcher = patch.object(mcc, name, target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_plan(self, move):
        def fake_export(engine, folder, output, fmt, ff, ffprobe, source_files=None):
            for file in (source_files or list(Path(folder).glob('*.flac'))):
                (output / Path(file).name).write_bytes(Path(file).read_bytes())
        patches = (
            patch.object(mcc.Organizer, '_export_release', fake_export),
            patch.object(mcc, 'release_identity', lambda folder, files, *args, **kw: {
                'folder': Path(folder).name, 'title': Path(folder).name, 'date': '2020-01-01',
                'catalog': '', 'barcode': '', 'physical': False, 'country': '', 'country_provenance': '',
                'release_type': 'Single', 'selected_release': 'test-only-id', 'metadata_verified': True,
                'notes': [], 'track_count': 1}),
            patch.object(mcc, 'ensure_ffmpeg', lambda: ('ff', 'ffprobe')),
            patch.object(mcc, '_update_copied_track_tags', lambda *a, **k: None),
            patch.object(mcc, 'collection_credit_consensus', lambda *a, **k: {}),
            patch.object(mcc, '_send_folders_to_recycle_bin', lambda folders: [__import__('shutil').rmtree(f) for f in folders]),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return mcc.organize_retained_plan(self.old_root, self.new_root, self.destination,
                                          self.releases, self.decisions, move, OPTIONS)

    def test_destination_inside_a_source_folder_is_refused(self):
        self.destination = self.old_root / 'UPDATED'
        with self.assertRaisesRegex(RuntimeError, 'outside the source'):
            self.run_plan(move=False)

    def test_copy_leaves_the_sources_untouched(self):
        result = self.run_plan(move=False)
        self.assertEqual(result['counts']['failed'], 0)
        self.assertFalse(result['source_folders_modified'])
        self.assertTrue(all((folder / '01 track.flac').is_file() for folder in self.sources))

    def test_move_recycles_only_the_releases_that_finished(self):
        result = self.run_plan(move=True)
        self.assertEqual(result['counts']['failed'], 0, result['problems'])
        self.assertEqual(result['source_folders_recycled'], 2 - result['counts']['partial'] - result['counts']['skipped'])
        self.assertEqual(any(folder.exists() for folder in self.sources),
                         result['source_folders_recycled'] < 2)

    def test_no_retained_release_is_an_error(self):
        self.decisions = [mcc.ReleaseDecision(d.release_id, 'DELETE', 'Dropped') for d in self.decisions]
        with self.assertRaisesRegex(RuntimeError, 'No retained'):
            self.run_plan(move=False)

    def test_undo_with_nothing_to_undo_says_so(self):
        with patch.object(mcc, '_last_manifest_path', lambda: self.destination / 'none.json'), \
                self.assertRaisesRegex(RuntimeError, 'Nothing to undo'):
            mcc.undo_last_run()

    def test_organizer_options_default_and_reject_unknown(self):
        self.assertEqual(mcc._organizer_options({}), mcc.ORGANIZER_OPTION_DEFAULTS)
        self.assertEqual(mcc._organizer_options({'organizer_options': {'format': 'FLAC', 'enable_checker': False}})['format'], 'FLAC')
        with self.assertRaises(ValueError):
            mcc._save_organizer_option('nonsense', True)


if __name__ == '__main__':
    unittest.main()
