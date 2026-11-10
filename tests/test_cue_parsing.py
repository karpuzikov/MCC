"""CUE sheets map tracks to the audio image with start and end times."""
from pathlib import Path
import tempfile
import unittest

from test_audio_safety import mcc

CUE_WITH_TWO_TRACKS = '''PERFORMER "Test Artist"
TITLE "Test Album"
FILE "album.flac" WAVE
  TRACK 01 AUDIO
    TITLE "First"
    INDEX 01 00:00:00
  TRACK 02 AUDIO
    TITLE "Second"
    PERFORMER "Guest Singer"
    INDEX 01 03:30:37
'''


class CueParsing(unittest.TestCase):
    def parse(self, cue_text):
        temp = tempfile.TemporaryDirectory(prefix='mcc-cue-')
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        image = folder / 'album.flac'
        image.write_bytes(b'audio image')
        cue = folder / 'album.cue'
        cue.write_text(cue_text, encoding='utf-8')
        return image, mcc._parse_cue_tracks(cue, [image])

    def test_tracks_get_numbers_titles_performers_and_start_end_times(self):
        image, tracks = self.parse(CUE_WITH_TWO_TRACKS)
        self.assertEqual([t['track_number'] for t in tracks], [1, 2])
        self.assertEqual([t['title'] for t in tracks], ['First', 'Second'])
        self.assertEqual([t['performer'] for t in tracks], ['', 'Guest Singer'])
        self.assertEqual({t['album'] for t in tracks}, {'Test Album'})
        self.assertEqual({t['album_performer'] for t in tracks}, {'Test Artist'})
        second_start = 3 * 60 + 30 + 37 / 75
        self.assertEqual(tracks[0]['start'], 0.0)
        self.assertAlmostEqual(tracks[0]['end'], second_start)
        self.assertAlmostEqual(tracks[1]['start'], second_start)
        self.assertEqual(tracks[1]['end'], 0.0)
        self.assertEqual({t['path'] for t in tracks}, {image})

    def test_a_track_without_index_01_is_dropped(self):
        _, tracks = self.parse(CUE_WITH_TWO_TRACKS.replace('    INDEX 01 03:30:37\n', ''))
        self.assertEqual([t['track_number'] for t in tracks], [1])


if __name__ == '__main__':
    unittest.main()
