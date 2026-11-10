"""Artist names keep every letter and symbol; only spelling noise is ignored."""
from types import SimpleNamespace
import unittest

from test_audio_safety import mcc

NON_LATIN_ARTISTS = ['Земфира', 'Кино', '宇多田ヒカル', 'أم كلثوم', 'ЛСП']
SYMBOL_ARTISTS = ['!!!', '†††', '$uicideboy$', 'Ke$ha', 'A$AP Rocky', 'P!nk', 'MØ', '+/-', '?']
ACCENTED_ARTISTS = ['Beyoncé', 'Björk', 'Mötley Crüe']


class ArtistNameKeys(unittest.TestCase):
    def test_names_in_any_script_get_distinct_keys(self):
        keys = [mcc.normalize_artist(name) for name in NON_LATIN_ARTISTS]
        self.assertNotIn('', keys)
        self.assertEqual(len(set(keys)), len(keys))

    def test_symbols_are_part_of_the_name(self):
        keys = [mcc.normalize_artist(name) for name in SYMBOL_ARTISTS]
        self.assertNotIn('', keys)
        self.assertEqual(len(set(keys)), len(keys))
        self.assertNotEqual(mcc.normalize_artist('P!nk'), mcc.normalize_artist('Pnk'))
        self.assertNotEqual(mcc.normalize_artist('$uicideboy$'), mcc.normalize_artist('uicideboy'))

    def test_spelling_variants_of_one_artist_share_a_key(self):
        variants = [
            ('Beyoncé', 'Beyonce'), ('Björk', 'Bjork'),
            ('AC/DC', 'AC_DC'), ('AC/DC', 'ACDC'), ('AC/DC', 'AC-DC'),
            ('R.E.M.', 'REM'), ('Guns N’ Roses', 'Guns N Roses'),
            ('Jay-Z', 'Jay Z'), ('Therapy?', 'Therapy'),
            ('Calvin Harris (feat. Rihanna)', 'Calvin Harris feat. Rihanna'),
            ('Noisia feat. Foreign Beggars', 'NOISIA'),
        ]
        for left, right in variants:
            with self.subTest(left=left, right=right):
                self.assertEqual(mcc.normalize_artist(left), mcc.normalize_artist(right))

    def test_featured_credit_spellings_in_an_artist_tag_share_a_signature(self):
        spellings = [
            'Calvin Harris feat. Rihanna', 'Calvin Harris ft. Rihanna',
            'Calvin Harris featuring Rihanna', 'Calvin Harris (feat. Rihanna)',
        ]
        self.assertEqual(len({frozenset(mcc._artist_signature(name)) for name in spellings}), 1)

    def test_ascii_names_keep_the_keys_they_had_before(self):
        expected = {
            'Noisia': 'noisia', 'AC/DC': 'acdc', 'Kanye West': 'kanyewest',
            'Various Artists': 'variousartists', 'deadmau5': 'deadmau5',
        }
        for name, key in expected.items():
            with self.subTest(name=name):
                self.assertEqual(mcc.normalize_artist(name), key)
        for alias_set in mcc._ARTIST_IDENTITY_ALIAS_SETS:
            for alias in alias_set:
                self.assertEqual(mcc.normalize_artist(alias), alias)

    def test_every_artist_key_builder_agrees_on_one_name(self):
        for name in NON_LATIN_ARTISTS + SYMBOL_ARTISTS + ACCENTED_ARTISTS + ['Noisia']:
            with self.subTest(name=name):
                key = mcc.normalize_artist(name)
                self.assertEqual(mcc._artist_signature(name), {key})
                self.assertEqual(mcc._primary_artist_key(SimpleNamespace(artist=name)), key)
        for name in SYMBOL_ARTISTS[2:5] + ACCENTED_ARTISTS:
            with self.subTest(featured=name):
                self.assertEqual(
                    mcc._featured_artists_from_text(f'Song (feat. {name})'),
                    {mcc.normalize_artist(name)},
                )

    def test_a_compilation_of_non_latin_artists_is_recognised(self):
        folder_artist = mcc.normalize_artist('Агата Кристи')
        self.assertTrue(mcc._other_artist_majority(
            ['Земфира', 'Кино', 'Сплин', 'Мумий Тролль'], folder_artist))
        self.assertTrue(mcc._single_artist_collection(['Земфира'] * 4))


if __name__ == '__main__':
    unittest.main()
