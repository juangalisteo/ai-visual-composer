"""The clip manifest marks the deleted clips (A2-I, PRUEBA-GS fallo 17)."""

import json

from app.modules.video_component import clip_batch


def _lease(tmp_path):
    clips = tmp_path / "video_clips"
    clips.mkdir()
    clip = clips / "scene_001.mkv"
    clip.write_bytes(b"ffv1")
    manifest = clips / "video_clips_manifest.json"
    manifest.write_text(
        json.dumps([{"scene": 1, "output_clip": str(clip), "kept": True}]),
        encoding="utf-8",
    )
    final = tmp_path / "final.mp4"
    final.write_bytes(b"mp4")
    return clip_batch.I2VArtifactLease.from_manifest(manifest), manifest, clip, final


def test_kept_true_becomes_false_once_the_clip_is_deleted(tmp_path):
    lease, manifest, clip, final = _lease(tmp_path)

    assert lease.cleanup_after_successful_public_render(final) == ()

    assert not clip.exists()
    assert json.loads(manifest.read_text(encoding="utf-8")) == [
        {"scene": 1, "output_clip": str(clip), "kept": False}
    ]


def test_a_manifest_that_cannot_be_marked_only_warns(tmp_path, capsys):
    lease, manifest, clip, final = _lease(tmp_path)
    manifest.write_text("no es json", encoding="utf-8")

    assert lease.cleanup_after_successful_public_render(final) == ()

    assert not clip.exists()
    screen = capsys.readouterr().out
    assert "ADVERTENCIA: No se pudo marcar en" in screen
    assert "El vídeo final está bien." in screen
    assert manifest.read_text(encoding="utf-8") == "no es json"


def test_a_clip_marked_as_deleted_is_never_owned_again(tmp_path):
    clips = tmp_path / "video_clips"
    clips.mkdir()
    clip = clips / "scene_001.mkv"
    clip.write_bytes(b"otro archivo con el mismo nombre")
    manifest = clips / "video_clips_manifest.json"
    manifest.write_text(
        json.dumps([{"scene": 1, "output_clip": str(clip), "kept": False}]),
        encoding="utf-8",
    )
    final = tmp_path / "final.mp4"
    final.write_bytes(b"mp4")

    lease = clip_batch.I2VArtifactLease.from_manifest(manifest)
    lease.cleanup_after_successful_public_render(final)

    assert lease.owned_lossless_paths == ()
    assert clip.read_bytes() == b"otro archivo con el mismo nombre"
