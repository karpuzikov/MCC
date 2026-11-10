"""Copy and Undo must report failures and never lose music."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from test_audio_safety import mcc


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
        # Never touch the real Undo manifest.
        self.manifest = root / 'undo.json'
        manifest_patch = patch.object(mcc, '_last_manifest_path', lambda: self.manifest)
        manifest_patch.start()
        self.addCleanup(manifest_patch.stop)

    def copy_all(self):
        return mcc.copy_retained_plan(self.old_root, self.new_root, self.destination,
                                      self.releases, self.decisions, 'all')

    def second_release_fails_to_copy(self):
        real_copytree = shutil.copytree

        def copytree_failing_for_second_release(source, staged, *args, **kwargs):
            if Path(source) == self.sources[1]:
                raise OSError('disk full')
            return real_copytree(source, staged, *args, **kwargs)
        return patch.object(shutil, 'copytree', copytree_failing_for_second_release)

    def test_failed_copy_removes_the_releases_it_already_copied(self):
        with self.second_release_fails_to_copy(), self.assertRaisesRegex(OSError, 'disk full'):
            self.copy_all()
        self.assertFalse((self.destination / 'Albums' / 'Edition 0').exists())
        self.assertTrue(all((folder / '01 track.flac').is_file() for folder in self.sources))

    def test_failed_cleanup_after_a_failed_copy_names_the_leftover_folder(self):
        copied_first_release = self.destination / 'Albums' / 'Edition 0'
        real_rmtree = shutil.rmtree

        def rmtree_refusing_the_copied_release(path, *args, **kwargs):
            if Path(path) == copied_first_release:
                raise PermissionError('locked by another program')
            return real_rmtree(path, *args, **kwargs)
        with self.second_release_fails_to_copy(), \
                patch.object(shutil, 'rmtree', rmtree_refusing_the_copied_release), \
                self.assertRaises(RuntimeError) as caught:
            self.copy_all()
        message = str(caught.exception)
        self.assertIn('disk full', message)
        self.assertIn(str(copied_first_release), message)
        self.assertIn('locked by another program', message)
        self.assertTrue((copied_first_release / '01 track.flac').is_file())

    def test_undo_reports_an_occupied_original_and_keeps_the_moved_music(self):
        mcc.move_retained_plan(self.old_root, self.new_root, self.destination, self.releases, self.decisions)
        moved_old_release = self.destination / 'Albums' / 'Edition 0'
        self.sources[0].mkdir(parents=True)  # something new took the original place
        restored, conflicts = mcc.undo_last_run()
        self.assertEqual(restored, 1)
        self.assertEqual(len(conflicts), 1)
        self.assertIn('Original path is occupied', conflicts[0])
        self.assertTrue((moved_old_release / '01 track.flac').is_file())
        self.assertTrue(self.manifest.is_file())  # kept so Undo can be retried


if __name__ == '__main__':
    unittest.main()
