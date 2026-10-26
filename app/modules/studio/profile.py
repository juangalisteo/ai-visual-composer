import math
from dataclasses import dataclass
from pathlib import Path

from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.shared.config_contract import (
    require_float,
    require_int,
    require_mapping,
    require_sequence,
    require_text,
)
from app.shared.operational_error import create_operational_error
from app.shared.profile_identity import (
    OperationalProfileKey,
    ProfileComponent,
)
from app.shared.subtitle_profile_identity import (
    ResolvedSubtitleProfile,
)


@dataclass(frozen=True)
class StudioMusicConfig:
    volume: float
    limiter_limit: float


@dataclass(frozen=True)
class StudioProfile:
    format: str
    profile_id: str
    video_extensions: tuple[str, ...]
    subtitle_extensions: tuple[str, ...]
    width: int
    height: int
    fps: int
    codec: str
    preset: str
    crf: int
    pixel_format: str
    movflags: str
    audio_codec: str
    audio_bitrate: str
    audio_sample_rate: int
    audio_channels: int
    max_duration_difference: float
    transition_duration: float
    music: StudioMusicConfig


@dataclass(frozen=True)
class StudioPreparation:
    profile_key: OperationalProfileKey
    profile: StudioProfile
    subtitle_profile: ResolvedSubtitleProfile | None
    video_path: Path
    subtitle_path: Path | None
    input_mode: str
    subtitles_enabled: bool = True
    subtitle_original: bool = False


class StudioProfileLoader:

    def load(self, profile, profile_key):
        if profile_key.component is not ProfileComponent.STUDIO:
            raise ValueError(
                "El perfil STUDIO requiere identidad component=studio."
            )
        if not isinstance(profile, dict):
            raise TypeError("El perfil STUDIO debe ser un diccionario.")

        self._require_identity(profile, profile_key)
        studio = require_mapping(profile, "studio", "studio")
        input_config = require_mapping(studio, "input", "studio.input")
        output = require_mapping(studio, "output", "studio.output")
        video = require_mapping(output, "video", "studio.output.video")
        audio = require_mapping(output, "audio", "studio.output.audio")
        validation = require_mapping(
            output,
            "validation",
            "studio.output.validation"
        )
        montage = require_mapping(studio, "montage", "studio.montage")
        music = require_mapping(studio, "music", "studio.music")

        width = require_int(output, "width", "studio.output.width")
        height = require_int(output, "height", "studio.output.height")
        fps = require_int(output, "fps", "studio.output.fps")
        crf = require_int(video, "crf", "studio.output.video.crf")
        audio_sample_rate = require_int(
            audio,
            "sample_rate",
            "studio.output.audio.sample_rate"
        )
        audio_channels = require_int(
            audio,
            "channels",
            "studio.output.audio.channels"
        )
        if width <= 0 or height <= 0 or fps <= 0:
            raise ValueError(
                "Las dimensiones y FPS de STUDIO deben ser positivos."
            )
        if crf < 0 or crf > 51:
            raise ValueError("El CRF de STUDIO debe estar entre 0 y 51.")
        if audio_sample_rate <= 0 or audio_channels not in {1, 2}:
            raise ValueError(
                "El audio STUDIO requiere sample_rate positivo y "
                "uno o dos canales."
            )
        transition_duration = require_float(
            montage,
            "transition_duration",
            "studio.montage.transition_duration"
        )
        if (
            not math.isfinite(transition_duration)
            or transition_duration <= 0
        ):
            raise ValueError(
                "studio.montage.transition_duration debe ser finita "
                "y mayor que cero."
            )

        music_config = StudioMusicConfig(
            volume=require_float(music, "volume", "studio.music.volume"),
            limiter_limit=require_float(
                music,
                "limiter_limit",
                "studio.music.limiter_limit"
            ),
        )
        self._validate_music(music_config)
        video_extensions = self._extensions(
            input_config,
            "video_extensions",
            "studio.input.video_extensions"
        )
        self._validate_video_extensions(video_extensions, profile_key)

        return StudioProfile(
            format=require_text(profile, "format", "format"),
            profile_id=require_text(profile, "profile_id", "profile_id"),
            video_extensions=video_extensions,
            subtitle_extensions=self._extensions(
                input_config,
                "subtitle_extensions",
                "studio.input.subtitle_extensions"
            ),
            width=width,
            height=height,
            fps=fps,
            codec=require_text(video, "codec", "studio.output.video.codec"),
            preset=require_text(video, "preset", "studio.output.video.preset"),
            crf=crf,
            pixel_format=require_text(
                video,
                "pixel_format",
                "studio.output.video.pixel_format"
            ),
            movflags=require_text(
                video,
                "movflags",
                "studio.output.video.movflags"
            ),
            audio_codec=require_text(audio, "codec", "studio.output.audio.codec"),
            audio_bitrate=require_text(audio, "bitrate", "studio.output.audio.bitrate"),
            audio_sample_rate=audio_sample_rate,
            audio_channels=audio_channels,
            max_duration_difference=require_float(
                validation,
                "max_duration_difference",
                "studio.output.validation.max_duration_difference"
            ),
            transition_duration=transition_duration,
            music=music_config,
        )

    def _require_identity(self, profile, profile_key):
        expected = {
            "component": profile_key.component.value,
            "format": profile_key.format,
            "profile_id": profile_key.profile_id,
        }
        actual = {key: profile.get(key) for key in expected}
        if actual != expected:
            raise ValueError(
                "La identidad interna del perfil STUDIO no coincide "
                "con la identidad operacional."
            )

    def _extensions(self, data, key, path):
        values = require_sequence(data, key, path)
        normalized = tuple(
            str(value).strip().lower()
            for value in values
        )
        if (
            not normalized
            or any(
                not value.startswith(".") or len(value) == 1
                for value in normalized
            )
            or len(set(normalized)) != len(normalized)
        ):
            raise ValueError(
                f"La configuración {path} debe contener extensiones únicas."
            )
        return normalized

    @staticmethod
    def _validate_video_extensions(video_extensions, profile_key):
        # SRT + VIDEO y MONTAJE pasan el vídeo a FFmpeg sin filtrar la
        # extensión; SOLO VIDEO lo transcribe con Whisper, que es el único
        # modo que la restringe.
        supported = ExternalMediaSubtitlePreparationService.SUPPORTED_EXTENSIONS
        unsupported = tuple(
            extension
            for extension in video_extensions
            if extension not in supported
        )
        if not unsupported:
            return

        error = ValueError(
            "studio.input.video_extensions incluye extensiones que Whisper "
            f"no admite: {', '.join(unsupported)}."
        )
        raise create_operational_error(
            family="CONFIG",
            user_message=(
                "studio.input.video_extensions incluye "
                f"{', '.join(unsupported)}, pero SOLO VIDEO transcribe el "
                "vídeo con Whisper, que solo admite "
                f"{', '.join(supported)}."
            ),
            recommended_action=(
                "Deja en studio.input.video_extensions solo "
                f"{', '.join(supported)}."
            ),
            operation="Validar perfil STUDIO",
            resource="/".join(
                (
                    profile_key.component.value,
                    profile_key.format,
                    profile_key.profile_id,
                )
            ),
        ) from error

    @staticmethod
    def _validate_music(config):
        if not 0 < config.volume <= 1:
            raise ValueError(
                "studio.music.volume debe estar entre 0 (exclusivo) y 1."
            )
        if not 0.0625 <= config.limiter_limit <= 1:
            raise ValueError(
                "studio.music.limiter_limit debe estar entre 0.0625 y 1."
            )
