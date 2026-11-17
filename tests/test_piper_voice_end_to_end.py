"""Focused configuration-to-public-audio tests for declarative Piper voices."""

import json
from pathlib import Path
import subprocess
import tempfile

import pytest

from app.modules.audio.piper_backend import PiperBackend
from app.modules.audio.piper_backend_provider import PiperBackendProvider
from app.modules.audio.tts_backend_registry import TtsBackendRegistry
from app.modules.audio.voice_builder import VoiceBuilder
from app.shared.config_manager import ConfigManager


_PIPER_DIR = Path(__file__).resolve().parents[1] / "models" / "audio" / "piper"


def _missing_voice_mark(voice_dir, model_name):
    return pytest.mark.skipif(
        not (_PIPER_DIR / voice_dir / model_name).is_file(),
        reason=f"Falta la voz Piper en models/audio/piper/{voice_dir}/.",
    )


VOICE_CASES = (
    pytest.param(
        "piper_davefx",
        22_050,
        marks=_missing_voice_mark("es_ES_davefx", "es_ES-davefx-medium.onnx"),
    ),
    pytest.param(
        "piper_carlfm",
        16_000,
        marks=_missing_voice_mark("es_ES_carlfm", "es_ES-carlfm-x_low.onnx"),
    ),
)


class _PiperVoiceDouble:
    def __init__(self, sample_rate_hz):
        self.config = type("Config", (), {"sample_rate": sample_rate_hz})()

    def synthesize(self, text, *, syn_config):
        del text, syn_config
        yield type(
            "Chunk",
            (),
            {
                "sample_rate": self.config.sample_rate,
                "sample_width": 2,
                "sample_channels": 1,
                "audio_int16_bytes": b"\x00\x00" * (self.config.sample_rate // 20),
            },
        )()


def _piper_backend_factory(project_root, observed_sample_rates, observed_timings):
    def piper_voice_factory(model_path, sidecar_path):
        del model_path
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sample_rate = sidecar["audio"]["sample_rate"]
        observed_sample_rates.append(sample_rate)
        return _PiperVoiceDouble(sample_rate)

    backend = PiperBackend(
        project_root,
        piper_voice_factory=piper_voice_factory,
        synthesis_config_factory=lambda **values: values,
    )
    synthesize = backend.synthesize

    def record_timings(request):
        result = synthesize(request)
        observed_timings.append(result.word_timings)
        return result

    backend.synthesize = record_timings
    return backend


@pytest.mark.parametrize(("voice_stem", "expected_sample_rate"), VOICE_CASES)
def test_declarative_piper_voice_flows_through_provider_backend_and_voice_builder(
    voice_stem,
    expected_sample_rate,
):
    project_root = Path(__file__).resolve().parents[1]
    observed_sample_rates = []
    observed_timings = []
    provider = PiperBackendProvider(
        project_root,
        backend_factory=lambda root: _piper_backend_factory(
            root,
            observed_sample_rates,
            observed_timings,
        ),
    )

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        workspace_parent = root / "workspaces"
        output_path = root / "audio" / "voz.mp3"
        builder = VoiceBuilder(
            config_manager=ConfigManager(voice_config_id=voice_stem),
            backend_registry=TtsBackendRegistry((provider,)),
            workspace_parent=workspace_parent,
        )
        result = builder.build(
            "La certificación técnica conserva puntuación y arquitectura.",
            output_path=output_path,
        )

        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,sample_rate,channels",
                "-of",
                "json",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        stream = json.loads(probe.stdout)["streams"][0]

        assert result == output_path
        assert output_path.is_file()
        assert output_path.stat().st_size > 0
        # Published at 44 100 Hz (MPEG-1) whatever the model rate.
        assert stream == {"codec_name": "mp3", "sample_rate": "44100", "channels": 1}
        assert tuple(workspace_parent.iterdir()) == ()
        assert provider.backend_key == "piper_onnx"
        assert observed_sample_rates == [expected_sample_rate]
        assert observed_timings == [None]


def test_piper_catalog_uses_no_fallback_and_default_voice_is_davefx():
    configuration = ConfigManager()

    default_voice = configuration.get_tts_voice_configuration().voice

    assert default_voice.voice_id == "piper_voice_davefx"
    assert default_voice.backend_key == "piper_onnx"
    assert default_voice.backend_options["synthesis"] == {"length_scale": 1.10}
