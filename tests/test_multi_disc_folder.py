"""One folder holding 3 CDs and a DVD named 1-01..., 2-01..., DVD-01... is not an incomplete release."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_audio_safety import mcc

FOLDER = Path('Music/[2011] BT - These Re-Imagined Machines [BHCD80BOX] 3CD+DVD')


def make_release(layout, tag_for):
    tracks = []
    for prefix, count in layout:
        for number in range(1, count + 1):
            tracks.append(mcc.Track(1, FOLDER / f'{prefix}-{number:02d}. BT - Song.flac', len(tracks),
                                    tags=tag_for(prefix, number, count)))
    return SimpleNamespace(tracks=tracks, validation_issues=[])


LAYOUT = [('1', 9), ('2', 8), ('3', 7), ('DVD', 64)]


class MultiDiscFolder(unittest.TestCase):
    def issues(self, tag_for, layout=LAYOUT):
        release = make_release(layout, tag_for)
        mcc.validate_release_track_totals([release])
        return release.validation_issues

    def test_per_disc_tags_without_disc_numbers_are_clean(self):
        self.assertEqual(self.issues(lambda p, n, c: {'TRACKNUMBER': str(n), 'TRACKTOTAL': str(c)}), [])

    def test_continuous_tag_numbers_do_not_matter_when_file_names_give_the_layout(self):
        counter = {'next': 0}

        def tags(prefix, number, count):
            counter['next'] += 1
            return {'TRACKNUMBER': str(counter['next']), 'TRACKTOTAL': str(count)}
        self.assertEqual(self.issues(tags), [])

    def test_missing_cd_track_is_still_reported_per_disc(self):
        declared = {'1': 9, '2': 8, '3': 7, 'DVD': 64}
        issues = self.issues(lambda p, n, c: {'TRACKNUMBER': str(n), 'TRACKTOTAL': str(declared[p])},
                             layout=[('1', 9), ('2', 8), ('3', 6), ('DVD', 64)])
        self.assertTrue(any('Disc 3' in issue and 'incomplete' in issue for issue in issues), issues)


if __name__ == '__main__':
    unittest.main()
