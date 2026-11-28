import json
import tempfile
import unittest
from pathlib import Path

from app.modules.video.media.media_loader import MediaLoader


class VideoClipManifestMediaLoaderTest(unittest.TestCase):

    def _base_files(
        self,
        root
    ):
        audio_path = root / "audio.mp3"
        subtitle_path = root / "subtitles.srt"
        output_path = root / "video" / "final.mp4"

        audio_path.write_bytes(
            b"audio"
        )
        subtitle_path.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nTexto",
            encoding="utf-8"
        )

        return audio_path, subtitle_path, output_path

    def test_loads_video_clips_ordered_by_scene(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            audio_path, subtitle_path, output_path = (
                self._base_files(
                    root
                )
            )
            first_clip = root / "scene_001.mp4"
            second_clip = root / "scene_002.mp4"
            first_clip.write_bytes(
                b"video-1"
            )
            second_clip.write_bytes(
                b"video-2"
            )
            manifest_path = root / "video_clips_manifest.json"
            storyboard_path = root / "storyboard.json"
            manifest_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 2,
                            "output_clip": str(
                                second_clip
                            ),
                            "duration_seconds": 2.5,
                        },
                        {
                            "scene": 1,
                            "output_clip": str(
                                first_clip
                            ),
                            "duration_seconds": 1.25,
                        },
                    ],
                    ensure_ascii=False,
                    indent=4,
                ),
                encoding="utf-8"
            )
            storyboard_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "duration": 3.0,
                            "visible_subject": "stone temple",
                        },
                        {
                            "scene": 2,
                            "duration": 4.5,
                            "visible_subject": "Tesla coil",
                            "visible_action": "electric sparks",
                            "key_objects": [
                                "electric generator",
                            ],
                        },
                    ]
                ),
                encoding="utf-8"
            )

            media = MediaLoader().load(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                images_manifest_path=manifest_path,
                output_path=output_path,
                media_manifest_type="video_clips",
                storyboard_path=storyboard_path
            )

        self.assertEqual(
            (
                first_clip,
                second_clip,
            ),
            media.image_paths
        )
        self.assertEqual(
            (
                "video",
                "video",
            ),
            media.media_types
        )
        self.assertEqual(
            (
                1.25,
                2.5,
            ),
            media.media_durations
        )
        self.assertEqual(
            (
                3.0,
                4.5,
            ),
            media.scene_durations
        )
        self.assertFalse(
            hasattr(
                media,
                "scene_metadata"
            )
        )

    def test_missing_clip_fails_clearly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            audio_path, subtitle_path, output_path = (
                self._base_files(
                    root
                )
            )
            manifest_path = root / "video_clips_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "output_clip": str(
                                root / "missing.mp4"
                            ),
                        },
                    ]
                ),
                encoding="utf-8"
            )

            with self.assertRaisesRegex(
                FileNotFoundError,
                "No existe el clip de vídeo"
            ):
                MediaLoader().load(
                    audio_path=audio_path,
                    subtitle_path=subtitle_path,
                    images_manifest_path=manifest_path,
                    output_path=output_path,
                    media_manifest_type="video_clips"
                )

    def test_clip_deleted_after_the_render_fails_clearly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_path, subtitle_path, output_path = self._base_files(root)
            kept_clip = root / "scene_001.mkv"
            kept_clip.write_bytes(b"ffv1")
            manifest_path = root / "video_clips_manifest.json"
            for kept, error in ((False, "se borró tras el render"), (True, None)):
                manifest_path.write_text(
                    json.dumps(
                        [{"scene": 1, "output_clip": str(kept_clip), "kept": kept}]
                    ),
                    encoding="utf-8",
                )
                options = {
                    "audio_path": audio_path,
                    "subtitle_path": subtitle_path,
                    "images_manifest_path": manifest_path,
                    "output_path": output_path,
                    "media_manifest_type": "video_clips",
                }
                with self.subTest(kept=kept):
                    if error is None:
                        media = MediaLoader().load(**options)
                        self.assertEqual((kept_clip,), tuple(media.image_paths))
                    else:
                        # Even if a file with that name is there again.
                        with self.assertRaisesRegex(FileNotFoundError, error):
                            MediaLoader().load(**options)

    def test_duplicate_scene_fails_clearly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )
            audio_path, subtitle_path, output_path = (
                self._base_files(
                    root
                )
            )
            clip = root / "scene_001.mp4"
            clip.write_bytes(
                b"video"
            )
            manifest_path = root / "video_clips_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "output_clip": str(
                                clip
                            ),
                        },
                        {
                            "scene": 1,
                            "output_clip": str(
                                clip
                            ),
                        },
                    ]
                ),
                encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ValueError,
                "duplicada"
            ):
                MediaLoader().load(
                    audio_path=audio_path,
                    subtitle_path=subtitle_path,
                    images_manifest_path=manifest_path,
                    output_path=output_path,
                    media_manifest_type="video_clips"
                )

    def test_allows_missing_subtitle_path_only_when_subtitles_are_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_path = root / "audio.mp3"
            audio_path.write_bytes(b"audio")
            image_path = root / "image.png"
            image_path.write_bytes(b"image")
            manifest_path = root / "images_manifest.json"
            manifest_path.write_text(
                json.dumps([{"scene": 1, "image": str(image_path)}]),
                encoding="utf-8",
            )

            media = MediaLoader().load(
                audio_path=audio_path,
                subtitle_path=None,
                images_manifest_path=manifest_path,
                output_path=root / "video" / "final.mp4",
                render_subtitles=False,
            )

        self.assertIsNone(media.subtitle_path)


if __name__ == "__main__":
    unittest.main()
