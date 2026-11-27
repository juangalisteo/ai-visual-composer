"""Quiet edges of each voice segment are cut before the join (A1, PRUEBA-GS fallo 4).

Chatterbox leaves silence, low noise and sometimes a short click at the end
of a segment: 1-2.5 s between segments instead of the declared pause.
"""

from array import array
import json
import math
from pathlib import Path
import sys
import wave

import pytest

from app.modules.audio.chatterbox_backend import ChatterboxBackend
from app.modules.audio.external_tts_process import (
    ExternalTtsProcess,
    SegmentTrim,
    SpeechSegment,
    join_segment_wavs,
    parse_segment_trim,
    trim_quiet_edges,
)
from app.modules.audio.tts_contracts import (
    ResolvedTtsVoice,
    TtsProsody,
    TtsSynthesisRequest,
    TtsSynthesisWorkspace,
    TtsVoiceConfigurationError,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RATE = 1000
TRIM = SegmentTrim(
    threshold_db=-40.0,
    window_seconds=0.02,
    keep_seconds=0.1,
    min_sound_seconds=0.15,
)


def _level(db, seconds):
    """Square wave whose RMS is ``db`` dBFS."""
    amplitude = round(32768 * 10 ** (db / 20))
    count = round(seconds * RATE)
    return [amplitude if index % 2 else -amplitude for index in range(count)]


def _silence(seconds):
    return [0] * round(seconds * RATE)


def _frames(*parts):
    samples = array("h", [value for part in parts for value in part])
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def _seconds(frames):
    return len(frames) / 2 / RATE


def test_silence_and_low_noise_at_both_edges_are_cut_keeping_the_margin():
    speech = _level(-12, 1.0)
    frames = _frames(_silence(0.5), _level(-50, 0.3), speech, _level(-45, 2.0))

    trimmed = trim_quiet_edges(frames, RATE, TRIM)

    assert trimmed == _frames(_level(-50, 0.1), speech, _level(-45, 0.1))


def test_a_short_burst_after_the_silence_counts_as_noise():
    speech = _level(-12, 1.0)
    frames = _frames(_level(-14, 0.06), _silence(0.4), speech, _silence(0.6), _level(-14, 0.07))

    trimmed = trim_quiet_edges(frames, RATE, TRIM)

    assert trimmed == _frames(_silence(0.1), speech, _silence(0.1))


def test_a_sound_as_long_as_the_minimum_is_speech():
    frames = _frames(_silence(0.6), _level(-14, 0.16), _silence(0.6))

    trimmed = trim_quiet_edges(frames, RATE, TRIM)

    assert trimmed == _frames(_silence(0.1), _level(-14, 0.16), _silence(0.1))


def test_short_quiet_gaps_and_short_sounds_inside_the_speech_are_kept():
    inside = (_level(-12, 0.3), _silence(0.2), _level(-14, 0.04), _silence(0.2), _level(-12, 0.3))
    frames = _frames(_silence(1.0), *inside, _silence(1.0))

    trimmed = trim_quiet_edges(frames, RATE, TRIM)

    assert trimmed == _frames(_silence(0.1), *inside, _silence(0.1))


def test_the_threshold_is_the_rms_of_each_window():
    speech = _level(-12, 0.5)
    noise_over = _level(-39, 0.5)
    noise_under = _level(-41, 0.5)

    assert trim_quiet_edges(_frames(speech, noise_over), RATE, TRIM) == _frames(
        speech, noise_over
    )
    assert trim_quiet_edges(_frames(speech, noise_under), RATE, TRIM) == _frames(
        speech, _level(-41, 0.1)
    )


def test_the_margin_never_goes_past_the_segment():
    frames = _frames(_silence(0.04), _level(-12, 0.5), _silence(0.02))

    assert trim_quiet_edges(frames, RATE, TRIM) == frames


@pytest.mark.parametrize(
    "frames",
    (
        _frames(_silence(2.0)),
        _frames(_level(-50, 2.0)),
        _frames(_silence(1.0), _level(-12, 0.1), _silence(1.0)),
    ),
)
def test_a_segment_without_speech_is_kept_whole(frames):
    assert trim_quiet_edges(frames, RATE, TRIM) == frames


def test_without_a_minimum_every_sound_counts():
    trim = SegmentTrim(-40.0, 0.02, 0.0, 0.0)
    frames = _frames(_silence(0.5), _level(-12, 0.02), _silence(0.5))

    assert trim_quiet_edges(frames, RATE, trim) == _frames(_level(-12, 0.02))


def _write_wav(path, frames):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(frames)


def test_join_cuts_the_edges_and_writes_the_declared_pause_between_segments(tmp_path):
    first = _frames(_silence(0.1), _level(-12, 1.0), _silence(0.6), _level(-14, 0.07))
    second = _frames(_silence(0.1), _level(-12, 2.0), _level(-45, 2.5))
    paths = (tmp_path / "1.wav", tmp_path / "2.wav")
    _write_wav(paths[0], first)
    _write_wav(paths[1], second)

    pauses = join_segment_wavs(
        segment_paths=paths,
        segments=(SpeechSegment("Uno.", 0.2), SpeechSegment("Dos.", 0.0)),
        output_path=tmp_path / "voz.wav",
        workspace=tmp_path,
        sample_rate_hz=RATE,
        segment_trim=TRIM,
    )

    with wave.open(str(tmp_path / "voz.wav"), "rb") as audio:
        joined = audio.readframes(audio.getnframes())
    assert joined == _frames(
        _silence(0.1), _level(-12, 1.0), _silence(0.1),
        _silence(0.2),
        _silence(0.1), _level(-12, 2.0), _level(-45, 0.1),
    )
    assert [(p.start_seconds, p.end_seconds) for p in pauses] == [(1.2, 1.4)]


def test_join_without_trim_keeps_every_frame(tmp_path):
    frames = _frames(_silence(1.0), _level(-12, 0.5), _silence(1.0))
    _write_wav(tmp_path / "1.wav", frames)

    join_segment_wavs(
        segment_paths=(tmp_path / "1.wav",),
        segments=(SpeechSegment("Uno.", 0.0),),
        output_path=tmp_path / "voz.wav",
        workspace=tmp_path,
        sample_rate_hz=RATE,
    )

    with wave.open(str(tmp_path / "voz.wav"), "rb") as audio:
        assert audio.readframes(audio.getnframes()) == frames


# --- configuration ------------------------------------------------------------

DECLARED = {
    "threshold_db": -40.0,
    "window_seconds": 0.02,
    "keep_seconds": 0.1,
    "min_sound_seconds": 0.15,
}


def test_declared_values_are_read():
    assert parse_segment_trim({"segment_trim": dict(DECLARED)}, required=True) == TRIM
    assert parse_segment_trim({"segment_trim": dict(DECLARED)}, required=False) == TRIM


def test_an_optional_block_that_is_absent_means_no_trim():
    assert parse_segment_trim({}, required=False) is None


def test_a_required_block_that_is_absent_is_a_configuration_error():
    with pytest.raises(TtsVoiceConfigurationError) as error:
        parse_segment_trim({}, required=True)

    assert str(error.value) == "backend_options.segment_trim debe ser un objeto; se recibió None."


@pytest.mark.parametrize("missing", sorted(DECLARED))
def test_every_value_is_required(missing):
    block = {key: value for key, value in DECLARED.items() if key != missing}

    with pytest.raises(TtsVoiceConfigurationError) as error:
        parse_segment_trim({"segment_trim": block}, required=False)

    assert str(error.value) == f"backend_options.segment_trim debe declarar {missing}."


def test_unknown_keys_are_rejected():
    with pytest.raises(TtsVoiceConfigurationError, match="no admite las claves: otra"):
        parse_segment_trim({"segment_trim": {**DECLARED, "otra": 1}}, required=True)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    (
        ("threshold_db", 0, "debe ser un nivel en dB menor que 0, como -40; se recibió 0."),
        ("threshold_db", 3.5, "debe ser un nivel en dB menor que 0, como -40; se recibió 3.5."),
        ("threshold_db", "-40", "debe ser un número; se recibió '-40'."),
        ("threshold_db", True, "debe ser un número; se recibió True."),
        ("threshold_db", float("-inf"), "debe ser un número; se recibió -inf."),
        ("window_seconds", 0, "debe ser mayor que 0 y como mucho 1; se recibió 0."),
        ("window_seconds", 1.5, "debe ser mayor que 0 y como mucho 1; se recibió 1.5."),
        ("window_seconds", -0.1, "debe ser un número mayor o igual que 0; se recibió -0.1."),
        ("keep_seconds", 1.01, "debe estar entre 0 y 1; se recibió 1.01."),
        ("keep_seconds", -1, "debe ser un número mayor o igual que 0; se recibió -1."),
        ("min_sound_seconds", 2, "debe estar entre 0 y 1; se recibió 2."),
        ("min_sound_seconds", None, "debe ser un número mayor o igual que 0; se recibió None."),
    ),
)
def test_values_out_of_range_are_rejected(key, value, message):
    with pytest.raises(TtsVoiceConfigurationError) as error:
        parse_segment_trim({"segment_trim": {**DECLARED, key: value}}, required=True)

    assert str(error.value) == f"backend_options.segment_trim.{key} {message}"


def test_edge_values_are_accepted():
    block = {"threshold_db": -0.5, "window_seconds": 1, "keep_seconds": 1, "min_sound_seconds": 0}

    assert parse_segment_trim({"segment_trim": block}, required=True) == SegmentTrim(
        -0.5, 1.0, 1.0, 0.0
    )


def test_only_chatterbox_declares_it_in_the_project():
    declared = {}
    for path in sorted((REPOSITORY_ROOT / "config" / "voice_configs").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        declared[path.stem] = document["backend_options"].get("segment_trim")

    assert declared.pop("chatterbox_multilingual") == DECLARED
    assert set(declared.values()) == {None}


# --- Chatterbox -----------------------------------------------------------------


def _chatterbox_project(tmp_path):
    (tmp_path / "env").mkdir()
    (tmp_path / "env" / "python.exe").write_bytes(b"python")
    weights = tmp_path / "weights"
    weights.mkdir()
    for name in (
        "ve.pt",
        "t3_mtl23ls_v2.safetensors",
        "s3gen.pt",
        "grapheme_mtl_merged_expanded_v1.json",
        "conds.pt",
    ):
        (weights / name).write_bytes(b"weights")
    return tmp_path


def _chatterbox_request(tmp_path, segment_trim):
    options = {
        "runtime": {
            "python_path": "env/python.exe",
            "cache_dir": "cache",
            "cuda_cache_dir": "cache/cuda",
            "temp_dir": "tmp/tts",
            "device": "cuda",
        },
        "model": {"checkpoint_dir": "weights"},
        "segmentation": {"max_characters": 10},
        "synthesis": {},
    }
    if segment_trim is not None:
        options["segment_trim"] = segment_trim
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return TtsSynthesisRequest(
        text="Primera frase. Segunda frase.",
        voice=ResolvedTtsVoice(
            voice_id="test_voice",
            backend_key="chatterbox_multilingual",
            backend_voice_id=None,
            language="es-ES",
            prosody=TtsProsody(sentence_pause_seconds=0.2, paragraph_pause_seconds=0.3),
            backend_options=options,
        ),
        workspace=TtsSynthesisWorkspace(workspace_id="test_workspace", path=workspace),
    )


def _noisy_worker(command, *, env, cwd, log_path, on_line):
    request = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
    log_path.write_text("", encoding="utf-8")
    for segment in request["segments"]:
        _write_wav(
            Path(segment["output"]),
            _frames(_silence(0.1), _level(-12, 1.0), _level(-45, 2.0), _level(-14, 0.07)),
        )
    Path(request["result"]).write_text(
        json.dumps({"status": "ok", "sample_rate": RATE}), encoding="utf-8"
    )
    return 0


def test_chatterbox_cuts_the_edges_of_its_segments(tmp_path):
    root = _chatterbox_project(tmp_path)
    backend = ChatterboxBackend(
        root,
        process=ExternalTtsProcess(
            launcher=_noisy_worker,
            progress=lambda done, total: None,
            base_environment={},
        ),
    )

    result = backend.synthesize(_chatterbox_request(root, dict(DECLARED)))

    with wave.open(str(result.staged_audio.path), "rb") as audio:
        seconds = audio.getnframes() / audio.getframerate()
    # (0.1 + 1.0 + 0.1) per segment and the 0.2 s pause between them.
    assert math.isclose(seconds, 1.2 + 0.2 + 1.2)
    assert [(p.start_seconds, p.end_seconds) for p in result.pauses] == [(1.2, 1.4)]


def test_chatterbox_without_segment_trim_is_a_configuration_error(tmp_path):
    root = _chatterbox_project(tmp_path)
    calls = []

    def worker(command, **kwargs):
        calls.append(command)
        return _noisy_worker(command, **kwargs)

    backend = ChatterboxBackend(
        root,
        process=ExternalTtsProcess(
            launcher=worker, progress=lambda done, total: None, base_environment={}
        ),
    )

    with pytest.raises(TtsVoiceConfigurationError, match="segment_trim debe ser un objeto"):
        backend.synthesize(_chatterbox_request(root, None))
    assert calls == []
