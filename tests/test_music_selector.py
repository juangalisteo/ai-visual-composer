import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.audio.music_selector import MusicSelector


class MusicSelectorTest(unittest.TestCase):

    def test_discovers_all_valid_tracks_deterministically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "ambient"
            second = root / "cinematic"
            first.mkdir()
            second.mkdir()
            expected = (
                first / "a.wav",
                first / "b.mp3",
                second / "c.flac",
            )
            for track in reversed(expected):
                track.write_bytes(b"audio")
            (first / "ignored.txt").write_text("ignored", encoding="utf-8")

            discovered = MusicSelector(root).discover_tracks()

        self.assertEqual(expected, discovered)

    def test_discovery_fails_clearly_without_tracks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "empty").mkdir()
            with self.assertRaisesRegex(FileNotFoundError, "pistas musicales"):
                MusicSelector(root).discover_tracks()

    def test_without_music_returns_none(self):
        self.assertIsNone(
            MusicSelector().select(
                None
            )
        )

    def test_random_selects_track_from_valid_category(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            calm = root / "calm"
            calm.mkdir()
            track = calm / "calm_001.mp3"
            track.write_bytes(
                b"audio"
            )

            with patch(
                "app.modules.audio.music_selector.random.choice",
                side_effect=lambda sequence: sequence[0]
            ), patch(
                "app.modules.audio.music_selector.ProgressLogger.info"
            ) as info_mock:
                selected = MusicSelector(
                    music_path=root
                ).select(
                    "random"
                )

        self.assertEqual(
            track,
            selected
        )
        info_mock.assert_called_once_with(
            "Música seleccionada: calm / calm_001.mp3"
        )

    def test_random_ignores_empty_categories_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            empty = root / "empty"
            invalid = root / "invalid"
            valid = root / "valid"
            empty.mkdir()
            invalid.mkdir()
            valid.mkdir()
            (
                invalid
                / "notes.txt"
            ).write_text(
                "not audio",
                encoding="utf-8"
            )
            expected_track = valid / "track.wav"
            expected_track.write_bytes(
                b"audio"
            )

            with patch(
                "app.modules.audio.music_selector.random.choice",
                side_effect=lambda sequence: sequence[0]
            ), patch(
                "app.modules.audio.music_selector.ProgressLogger.info"
            ):
                selected = MusicSelector(
                    music_path=root
                ).select(
                    "random"
                )

        self.assertEqual(
            expected_track,
            selected
        )

    def test_random_ignores_hidden_and_temporary_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            category = root / "ambient"
            category.mkdir()
            (
                category
                / ".hidden.mp3"
            ).write_bytes(
                b"hidden"
            )
            (
                category
                / "~temp.mp3"
            ).write_bytes(
                b"temp"
            )
            (
                category
                / "draft.tmp"
            ).write_bytes(
                b"temp"
            )
            expected_track = category / "ambient_001.flac"
            expected_track.write_bytes(
                b"audio"
            )

            with patch(
                "app.modules.audio.music_selector.random.choice",
                side_effect=lambda sequence: sequence[0]
            ), patch(
                "app.modules.audio.music_selector.ProgressLogger.info"
            ):
                selected = MusicSelector(
                    music_path=root
                ).select(
                    "random"
                )

        self.assertEqual(
            expected_track,
            selected
        )

    def test_random_fails_when_no_valid_tracks_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            empty = root / "empty"
            empty.mkdir()

            with self.assertRaises(
                FileNotFoundError
            ):
                MusicSelector(
                    music_path=root
                ).select(
                    "random"
                )

    def test_random_can_choose_any_valid_category_deterministically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            (
                first
                / "first.mp3"
            ).write_bytes(
                b"audio"
            )
            expected_track = second / "second.mp3"
            expected_track.write_bytes(
                b"audio"
            )

            with patch(
                "app.modules.audio.music_selector.random.choice",
                side_effect=lambda sequence: sequence[-1]
            ), patch(
                "app.modules.audio.music_selector.ProgressLogger.info"
            ):
                selected = MusicSelector(
                    music_path=root
                ).select(
                    "random"
                )

        self.assertEqual(
            expected_track,
            selected
        )


if __name__ == "__main__":
    unittest.main()
