"""Track titles in any script get real keys; Latin titles keep their old keys."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_audio_safety import mcc

NON_LATIN_TITLES = ['Привет, мир', 'Звезда по имени Солнце', '夜に駆ける', 'مرحبا بالعالم']


def make_track(title, explicit, artist='Artist', name=None):
    return mcc.Track(1, Path(name or f'{explicit}.flac'), 1, title=title, artist=artist,
                     explicit=explicit, duration=200, fingerprint=None)


class TitleKeys(unittest.TestCase):
    def test_titles_in_any_script_get_distinct_keys(self):
        keys = [mcc.identity_title(t) for t in NON_LATIN_TITLES]
        self.assertNotIn('', keys)
        self.assertEqual(len(set(keys)), len(keys))

    def test_punctuation_and_case_do_not_change_a_key(self):
        self.assertEqual(mcc.identity_title('Привет, мир'), mcc.identity_title('привет мир!'))
        self.assertEqual(mcc.identity_title('Ёлка'), mcc.identity_title('елка'))
        self.assertEqual(mcc.identity_title('夜に駆ける'), mcc.identity_title('夜に、駆ける'))

    def test_latin_keys_are_unchanged(self):
        self.assertEqual(mcc.identity_title('Hello, World!'), 'helloworld')
        self.assertEqual(mcc.identity_title('Hello World (2011 Remaster)'), 'helloworld')
        self.assertEqual(mcc.compact_title_key('Don’t Stop 99'), 'dontstop99')

    def test_clean_twin_of_a_non_latin_title_is_excluded(self):
        explicit = make_track('Привет, мир', 'explicit')
        clean = make_track('Привет, мир', 'clean')
        other = make_track('Другая песня', 'clean', name='other.flac')
        mcc._apply_explicit_over_clean_tracks([explicit, clean, other])
        self.assertTrue(clean.exclude_from_coverage)
        self.assertFalse(explicit.exclude_from_coverage)
        self.assertFalse(other.exclude_from_coverage)

    def test_censor_masks_match_in_any_script(self):
        self.assertTrue(mcc.masked_title_compatible('Hello Wor**d', 'Hello World'))
        self.assertTrue(mcc.masked_title_compatible('Пр**ет', 'Привет'))
        self.assertFalse(mcc.masked_title_compatible('Пр**ет', 'Прощай'))


class PersonalPicks(unittest.TestCase):
    def test_non_latin_pick_is_not_empty(self):
        self.assertEqual(mcc._personal_pick_normalize('Инструментал'), 'инструментал')
        self.assertNotEqual(mcc._personal_pick_normalize('夜に駆ける'), '')

    def test_non_latin_pick_matches_by_contains_and_exact(self):
        track = SimpleNamespace(display_title='Звезда (Инструментал)', path=Path('01 Звезда (Инструментал).flac'))
        self.assertTrue(mcc._personal_pick_match(track, [{'mode': 'contains', 'value': 'инструментал'}]))
        self.assertFalse(mcc._personal_pick_match(track, [{'mode': 'exact', 'value': 'инструментал'}]))
        self.assertTrue(mcc._personal_pick_match(track, [{'mode': 'exact', 'value': 'Звезда Инструментал'}]))
        self.assertFalse(mcc._personal_pick_match(track, [{'mode': 'contains', 'value': 'живая'}]))


class CreditNames(unittest.TestCase):
    def track(self):
        return SimpleNamespace(artist='Кино', album_artist='Кино')

    def test_two_word_possessor_counts_in_any_script(self):
        latin = mcc._confident_possessive_remix_descriptor(self.track(), "Simon Hale's Orchestrata")
        cyrillic = mcc._confident_possessive_remix_descriptor(self.track(), "Иван Петров's Orchestrata")
        self.assertTrue(latin)
        self.assertEqual(latin, cyrillic)

    def test_one_word_possessor_stays_conservative(self):
        self.assertFalse(mcc._confident_possessive_remix_descriptor(self.track(), "Brian's First Drive"))
        self.assertFalse(mcc._confident_possessive_remix_descriptor(self.track(), "Иван's First Drive"))


if __name__ == '__main__':
    unittest.main()
