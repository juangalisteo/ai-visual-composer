"""Focused contract tests for the isolated Piper TTS backend."""

from pathlib import Path
from types import SimpleNamespace
import json
import re
import sys
import wave

import pytest

from app.modules.audio import piper_backend
from app.modules.audio.piper_backend import PiperBackend
from app.modules.audio.tts_backend_registry import TtsBackend
from app.modules.audio.tts_contracts import (
    ResolvedTtsVoice,
    TtsBackendError,
    TtsBackendErrorKind,
    TtsPause,
    TtsProsody,
    TtsSynthesisRequest,
    TtsSynthesisWorkspace,
)


CHUNK_FRAMES = 8


class FakePiperVoice:
    """Yield one non-silent chunk per ``.``/``?``/``!`` sentence, like Piper."""

    def __init__(self, sample_rate=22050, *, synthesize_error=None, audio_format=None):
        self.config = SimpleNamespace(sample_rate=sample_rate)
        self.synthesize_error = synthesize_error
        self.audio_format = audio_format or (1, 2, sample_rate)
        self.calls = []

    def synthesize(self, text, syn_config=None):
        self.calls.append((text, syn_config))
        if self.synthesize_error is not None:
            raise self.synthesize_error
        channels, sample_width, sample_rate = self.audio_format
        for _sentence in re.findall(r"[^.?!]+[.?!]*", text):
            yield SimpleNamespace(
                sample_rate=sample_rate,
                sample_width=sample_width,
                sample_channels=channels,
                audio_int16_bytes=b"\x01" * sample_width * channels * CHUNK_FRAMES,
            )


class EmptyPiperVoice(FakePiperVoice):
    def synthesize(self, text, syn_config=None):
        self.calls.append((text, syn_config))
        return iter(())


class RecordingFactory:
    def __init__(self, voice=None, error=None):
        self.voice = voice or FakePiperVoice()
        self.error = error
        self.calls = []

    def __call__(self, model_path, sidecar_path):
        self.calls.append((model_path, sidecar_path))
        if self.error is not None:
            raise self.error
        return self.voice


class RecordingConfigFactory:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(**kwargs)


def _write_model_pair(root, *, model_length_scale=1.0, model_language="es"):
    relative = Path("models/audio/piper/fixture/voice.onnx")
    model_path = root / relative
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"onnx")
    Path(f"{model_path}.json").write_text(
        json.dumps(
            {
                "espeak": {"voice": model_language},
                "inference": {"length_scale": model_length_scale},
            }
        ),
        encoding="utf-8",
    )
    return relative, model_path


def _request(tmp_path, relative_path, *, backend_key="piper_onnx", language="es-ES", backend_voice_id=None, synthesis=None, speaking_rate=1.0, volume_gain_db=0.0, text="Texto de prueba.", sentence_pause_seconds=0.0, paragraph_pause_seconds=0.0):
    options = {"model": {"onnx_path": str(relative_path)}}
    if synthesis is not None:
        options["synthesis"] = synthesis
    return TtsSynthesisRequest(
        text=text,
        voice=ResolvedTtsVoice(
            voice_id="test_voice",
            backend_key=backend_key,
            backend_voice_id=backend_voice_id,
            language=language,
            prosody=TtsProsody(
                speaking_rate=speaking_rate,
                volume_gain_db=volume_gain_db,
                sentence_pause_seconds=sentence_pause_seconds,
                paragraph_pause_seconds=paragraph_pause_seconds,
            ),
            backend_options=options,
        ),
        workspace=TtsSynthesisWorkspace(
            workspace_id="piper-test",
            path=tmp_path / "workspace",
        ),
    )


def _backend(root, voice=None, *, error=None, config_factory=None):
    factory = RecordingFactory(voice=voice, error=error)
    config_factory = config_factory or RecordingConfigFactory()
    return (
        PiperBackend(
            root,
            piper_voice_factory=factory,
            synthesis_config_factory=config_factory,
        ),
        factory,
        config_factory,
    )


def _assert_kind(error, kind):
    assert error.value.diagnostic.kind is kind
    assert error.value.__cause__ is not None


def test_valid_request_produces_native_wav_staging_without_word_timings(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    voice = FakePiperVoice(sample_rate=22050)
    backend, factory, config_factory = _backend(tmp_path, voice)

    result = backend.synthesize(_request(tmp_path, relative))

    assert isinstance(backend, TtsBackend)
    assert result.word_timings is None
    assert result.staged_audio.container == "wav"
    assert result.staged_audio.codec == "pcm_s16le"
    assert result.staged_audio.channels == 1
    assert result.staged_audio.sample_rate_hz == 22050
    assert result.staged_audio.path.is_file()
    assert result.staged_audio.path.parent == tmp_path / "workspace"
    assert factory.calls == [
        (tmp_path / relative, Path(f"{tmp_path / relative}.json"))
    ]
    assert config_factory.calls == [
        {
            "speaker_id": None,
            "length_scale": None,
            "noise_scale": None,
            "noise_w_scale": None,
            "normalize_audio": True,
            "volume": 1.0,
        }
    ]


def test_rejects_request_for_another_backend(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, factory, _ = _backend(tmp_path)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, relative, backend_key="different_backend"))

    assert error.value.diagnostic.kind is TtsBackendErrorKind.CONFIGURATION
    assert factory.calls == []


@pytest.mark.parametrize(
    "declared_path",
    [
        "C:/outside/voice.onnx",
        "models/audio/piper/../../outside/voice.onnx",
        "models/audio/not-piper/voice.onnx",
        "models/audio/piper/fixture/voice.bin",
    ],
)
def test_rejects_unsafe_or_non_onnx_declared_paths(tmp_path, declared_path):
    _write_model_pair(tmp_path)
    backend, factory, _ = _backend(tmp_path)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, declared_path))

    _assert_kind(error, TtsBackendErrorKind.CONFIGURATION)
    assert factory.calls == []


def test_rejects_missing_model_as_resource_unavailable(tmp_path):
    relative = Path("models/audio/piper/fixture/missing.onnx")
    backend, factory, _ = _backend(tmp_path)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, relative))

    _assert_kind(error, TtsBackendErrorKind.RESOURCE_UNAVAILABLE)
    assert factory.calls == []


def test_rejects_missing_sidecar_as_resource_unavailable(tmp_path):
    relative = Path("models/audio/piper/fixture/voice.onnx")
    model_path = tmp_path / relative
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"onnx")
    backend, factory, _ = _backend(tmp_path)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, relative))

    _assert_kind(error, TtsBackendErrorKind.RESOURCE_UNAVAILABLE)
    assert factory.calls == []


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"model": {}},
        {"model": {"onnx_path": "models/audio/piper/fixture/voice.onnx", "unexpected": 1}},
        {"model": {"onnx_path": "models/audio/piper/fixture/voice.onnx"}, "unexpected": {}},
        {"model": {"onnx_path": "models/audio/piper/fixture/voice.onnx"}, "synthesis": None},
        {"model": {"onnx_path": "models/audio/piper/fixture/voice.onnx"}, "synthesis": {"unknown": 1}},
    ],
)
def test_rejects_invalid_piper_namespace(tmp_path, options):
    _write_model_pair(tmp_path)
    voice = ResolvedTtsVoice(
        voice_id="test_voice",
        backend_key="piper_onnx",
        backend_voice_id=None,
        language="es-ES",
        backend_options=options,
    )
    request = TtsSynthesisRequest(
        text="Texto.",
        voice=voice,
        workspace=TtsSynthesisWorkspace("test", tmp_path / "workspace"),
    )
    backend, factory, _ = _backend(tmp_path)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(request)

    _assert_kind(error, TtsBackendErrorKind.CONFIGURATION)
    assert factory.calls == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("length_scale", 0),
        ("noise_scale", -0.1),
        ("noise_w_scale", -0.1),
        ("volume", -0.1),
        ("normalize_audio", 1),
    ],
)
def test_rejects_invalid_synthesis_values(tmp_path, field, value):
    relative, _ = _write_model_pair(tmp_path)
    backend, factory, _ = _backend(tmp_path)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, relative, synthesis={field: value}))

    _assert_kind(error, TtsBackendErrorKind.CONFIGURATION)
    assert factory.calls == []


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_common_neutral_contract_rejects_nonfinite_backend_options_before_piper(value):
    with pytest.raises(ValueError):
        ResolvedTtsVoice(
            voice_id="test_voice",
            backend_key="piper_onnx",
            backend_voice_id=None,
            language="es-ES",
            backend_options={
                "model": {"onnx_path": "models/audio/piper/fixture/voice.onnx"},
                "synthesis": {"length_scale": value},
            },
        )


def test_rejects_backend_voice_id_for_mono_speaker_piper(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, factory, _ = _backend(tmp_path)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, relative, backend_voice_id="not-an-index"))

    assert error.value.diagnostic.kind is TtsBackendErrorKind.CONFIGURATION
    assert factory.calls == []


def test_compares_language_primary_subtags_without_voice_name_logic(tmp_path):
    relative, _ = _write_model_pair(tmp_path, model_language="es")
    backend, _, _ = _backend(tmp_path)

    result = backend.synthesize(_request(tmp_path, relative, language="es-ES"))

    assert result.staged_audio.path.is_file()


def test_rejects_incompatible_language(tmp_path):
    relative, _ = _write_model_pair(tmp_path, model_language="es")
    backend, factory, _ = _backend(tmp_path)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, relative, language="fr-FR"))

    _assert_kind(error, TtsBackendErrorKind.CONFIGURATION)
    assert factory.calls == []


def test_uses_explicit_sidecar_and_cpu_in_default_piper_loader(monkeypatch, tmp_path):
    calls = []

    class FakePiperVoice:
        @staticmethod
        def load(*args, **kwargs):
            calls.append((args, kwargs))
            return object()

    monkeypatch.setitem(sys.modules, "piper", SimpleNamespace(PiperVoice=FakePiperVoice))

    result = piper_backend._default_piper_voice_factory(
        tmp_path / "voice.onnx",
        tmp_path / "voice.onnx.json",
    )

    assert result is not None
    assert calls == [
        (
            (tmp_path / "voice.onnx",),
            {"config_path": tmp_path / "voice.onnx.json", "use_cuda": False},
        )
    ]


def test_explicit_length_scale_wins_over_neutral_speaking_rate(tmp_path):
    relative, _ = _write_model_pair(tmp_path, model_length_scale=1.7)
    backend, _, configs = _backend(tmp_path)

    backend.synthesize(
        _request(
            tmp_path,
            relative,
            speaking_rate=2.0,
            synthesis={"length_scale": 1.25},
        )
    )

    assert configs.calls[0]["length_scale"] == 1.25


def test_non_neutral_speaking_rate_uses_model_default_not_literal_one(tmp_path):
    relative, _ = _write_model_pair(tmp_path, model_length_scale=1.8)
    backend, _, configs = _backend(tmp_path)

    backend.synthesize(_request(tmp_path, relative, speaking_rate=1.5))

    assert configs.calls[0]["length_scale"] == pytest.approx(1.2)


def test_explicit_volume_wins_over_neutral_gain(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, _, configs = _backend(tmp_path)

    backend.synthesize(
        _request(
            tmp_path,
            relative,
            volume_gain_db=12.0,
            synthesis={"volume": 0.4},
        )
    )

    assert configs.calls[0]["volume"] == 0.4


def test_volume_gain_db_maps_once_to_piper_linear_multiplier(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, _, configs = _backend(tmp_path)

    backend.synthesize(_request(tmp_path, relative, volume_gain_db=6.0))

    assert configs.calls[0]["volume"] == pytest.approx(10 ** (6.0 / 20))


def test_passes_supported_synthesis_overrides_and_no_speaker_id(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, _, configs = _backend(tmp_path)

    backend.synthesize(
        _request(
            tmp_path,
            relative,
            synthesis={
                "noise_scale": 0.3,
                "noise_w_scale": 0.4,
                "normalize_audio": False,
            },
        )
    )

    assert configs.calls[0] == {
        "speaker_id": None,
        "length_scale": None,
        "noise_scale": 0.3,
        "noise_w_scale": 0.4,
        "normalize_audio": False,
        "volume": 1.0,
    }


@pytest.mark.parametrize("sample_rate", [22050, 16000])
def test_preserves_native_sample_rate_without_resampling(tmp_path, sample_rate):
    relative, _ = _write_model_pair(tmp_path)
    voice = FakePiperVoice(sample_rate=sample_rate)
    backend, _, _ = _backend(tmp_path, voice)

    result = backend.synthesize(_request(tmp_path, relative))

    with wave.open(str(result.staged_audio.path), "rb") as wav_file:
        assert wav_file.getframerate() == sample_rate
    assert result.staged_audio.sample_rate_hz == sample_rate


def test_load_failure_is_resource_unavailable_with_cause(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, _, _ = _backend(tmp_path, error=RuntimeError("onnx failure"))

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, relative))

    _assert_kind(error, TtsBackendErrorKind.RESOURCE_UNAVAILABLE)
    assert isinstance(error.value.__cause__, RuntimeError)


def test_synthesis_failure_is_preserved_without_fallback(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    voice = FakePiperVoice(synthesize_error=RuntimeError("synthesis failure"))
    backend, factory, _ = _backend(tmp_path, voice)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, relative))

    _assert_kind(error, TtsBackendErrorKind.SYNTHESIS)
    assert isinstance(error.value.__cause__, RuntimeError)
    assert len(factory.calls) == 1


@pytest.mark.parametrize(
    "voice",
    [
        EmptyPiperVoice(),
        FakePiperVoice(audio_format=(2, 2, 22050)),
        FakePiperVoice(audio_format=(1, 1, 22050)),
        FakePiperVoice(audio_format=(1, 2, 16000)),
    ],
)
def test_invalid_generated_wav_is_audio_invalid_with_cause(tmp_path, voice):
    relative, _ = _write_model_pair(tmp_path)
    backend, _, _ = _backend(tmp_path, voice)

    with pytest.raises(TtsBackendError) as error:
        backend.synthesize(_request(tmp_path, relative))

    _assert_kind(error, TtsBackendErrorKind.AUDIO_INVALID)


def test_each_request_loads_its_declared_model_without_cache(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, factory, _ = _backend(tmp_path)

    backend.synthesize(_request(tmp_path, relative))
    backend.synthesize(_request(tmp_path, relative))

    assert len(factory.calls) == 2


def test_does_not_select_model_from_voice_identity_or_filename_substrings(tmp_path):
    relative, model_path = _write_model_pair(tmp_path)
    backend, factory, _ = _backend(tmp_path)
    request = _request(tmp_path, relative)
    request = TtsSynthesisRequest(
        text=request.text,
        voice=ResolvedTtsVoice(
            voice_id="not_a_product_voice",
            backend_key=request.voice.backend_key,
            backend_voice_id=None,
            language=request.voice.language,
            prosody=request.voice.prosody,
            backend_options=request.voice.backend_options,
        ),
        workspace=request.workspace,
    )

    backend.synthesize(request)

    assert factory.calls[0][0] == model_path


@pytest.mark.parametrize(
    ("text", "paragraphs"),
    [
        ("Una. Dos.", ("Una. Dos.",)),
        ("Línea uno\nlínea dos.", ("Línea uno\nlínea dos.",)),
        ("Uno.\n\nDos.", ("Uno.", "Dos.")),
        ("Uno.\r\n\r\nDos.\r\nTres.", ("Uno.", "Dos.\nTres.")),
        ("Uno.\n \t\n\n\nDos.", ("Uno.", "Dos.")),
        ("\n\nUno.\n\n", ("Uno.",)),
    ],
)
def test_splits_paragraphs_only_at_blank_lines(text, paragraphs):
    assert piper_backend._split_paragraphs(text) == paragraphs


@pytest.mark.parametrize(
    ("paragraph", "pieces"),
    [
        ("Una. Dos.", ("Una. Dos.",)),
        ("Espera… Ya llega.", ("Espera…", "Ya llega.")),
        ("Espera... ya llega.", ("Espera...", "ya llega.")),
        ("¿Y si…? Bien.", ("¿Y si…?", "Bien.")),
        ("Dijo «así…» y calló.", ("Dijo «así…»", "y calló.")),
        ("Termina así…", ("Termina así…",)),
        ("Uno…dos.", ("Uno…dos.",)),
    ],
)
def test_cuts_after_ellipses_that_espeak_does_not_end(paragraph, pieces):
    assert piper_backend._split_after_ellipses(paragraph) == pieces


def _frames(path):
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.readframes(wav_file.getnframes())


def _silence_runs(frames):
    """Length in samples of each run of zero samples between audio chunks."""
    samples = [frames[index : index + 2] for index in range(0, len(frames), 2)]
    runs, current = [], 0
    for sample in samples:
        if sample == b"\x00\x00":
            current += 1
        elif current:
            runs.append(current)
            current = 0
    assert current == 0, "no silence must be written after the last chunk"
    return runs


@pytest.mark.parametrize("sample_rate", [22050, 16000])
def test_writes_exact_sentence_and_paragraph_pauses_between_chunks(tmp_path, sample_rate):
    relative, _ = _write_model_pair(tmp_path)
    voice = FakePiperVoice(sample_rate=sample_rate)
    backend, _, _ = _backend(tmp_path, voice)

    result = backend.synthesize(
        _request(
            tmp_path,
            relative,
            text="Uno. ¿Dos? ¡Tres!\r\n\r\nCuatro…  cinco.\n\n\nSeis",
            sentence_pause_seconds=0.5,
            paragraph_pause_seconds=1.5,
        )
    )

    frames = _frames(result.staged_audio.path)
    sentence, paragraph = round(0.5 * sample_rate), round(1.5 * sample_rate)
    assert frames[: 2 * CHUNK_FRAMES] == b"\x01" * 2 * CHUNK_FRAMES
    assert _silence_runs(frames) == [sentence, sentence, paragraph, sentence, paragraph]
    assert len(frames) == 2 * (6 * CHUNK_FRAMES + 3 * sentence + 2 * paragraph)
    assert [text for text, _ in voice.calls] == [
        "Uno. ¿Dos? ¡Tres!",
        "Cuatro…",
        "cinco.",
        "Seis",
    ]
    chunk, sentence_s, paragraph_s = CHUNK_FRAMES / sample_rate, 0.5, 1.5
    starts = []
    position = 0.0
    for pause in (sentence_s, sentence_s, paragraph_s, sentence_s, paragraph_s):
        position += chunk
        starts.append((position, position + pause))
        position += pause
    assert len(result.pauses) == 5
    assert all(isinstance(pause, TtsPause) for pause in result.pauses)
    for pause, (start, end) in zip(result.pauses, starts):
        assert pause.start_seconds == pytest.approx(start)
        assert pause.end_seconds == pytest.approx(end)


def test_zero_pauses_write_chunks_back_to_back(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    voice = FakePiperVoice()
    backend, _, _ = _backend(tmp_path, voice)

    result = backend.synthesize(
        _request(tmp_path, relative, text="Uno. Dos.\n\nTres… cuatro.")
    )

    frames = _frames(result.staged_audio.path)
    assert frames == b"\x01" * 2 * 4 * CHUNK_FRAMES
    assert _silence_runs(frames) == []
    assert result.pauses == ()


def test_text_without_blank_lines_only_gets_sentence_pauses(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, _, _ = _backend(tmp_path, FakePiperVoice())

    result = backend.synthesize(
        _request(
            tmp_path,
            relative,
            text="Uno. Dos\ntres. Cuatro.",
            sentence_pause_seconds=0.25,
            paragraph_pause_seconds=2.0,
        )
    )

    assert _silence_runs(_frames(result.staged_audio.path)) == [
        round(0.25 * 22050)
    ] * 2


def test_paragraph_pause_does_not_add_the_sentence_pause(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, _, _ = _backend(tmp_path, FakePiperVoice())

    result = backend.synthesize(
        _request(
            tmp_path,
            relative,
            text="Uno.\n\nDos.",
            sentence_pause_seconds=0.5,
            paragraph_pause_seconds=0.0,
        )
    )

    assert _silence_runs(_frames(result.staged_audio.path)) == []


def test_reported_pauses_are_the_exact_written_samples(tmp_path):
    relative, _ = _write_model_pair(tmp_path)
    backend, _, _ = _backend(tmp_path, FakePiperVoice(sample_rate=16000))

    result = backend.synthesize(
        _request(
            tmp_path,
            relative,
            text="Uno. Dos.\n\nTres.",
            sentence_pause_seconds=0.25,
            paragraph_pause_seconds=1.0,
        )
    )

    assert result.pauses == (
        TtsPause(CHUNK_FRAMES / 16000, (CHUNK_FRAMES + 4000) / 16000),
        TtsPause((2 * CHUNK_FRAMES + 4000) / 16000, (2 * CHUNK_FRAMES + 20000) / 16000),
    )
