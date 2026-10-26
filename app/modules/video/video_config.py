from dataclasses import dataclass

from app.shared.config_manager import ConfigManager
from app.shared.config_contract import (
    require_int,
    require_mapping,
    require_text,
)

from app.modules.video.config.motion_config import MotionConfig
from app.modules.video.config.transition_config import TransitionConfig
from app.modules.video.config.overlay_config import OverlayConfig
from app.modules.video.config.visual_effect_config import (
    VisualEffectConfig
)
from app.modules.video.config.fade_config import FadeConfig
from app.modules.video.config.subtitle_config import SubtitleConfig
from app.modules.video.config.validation_config import ValidationConfig

from app.modules.video.config.loaders.motion_loader import (
    MotionConfigLoader
)
from app.modules.video.config.loaders.transition_loader import (
    TransitionConfigLoader
)
from app.modules.video.config.loaders.overlay_loader import (
    OverlayConfigLoader
)
from app.modules.video.config.loaders.visual_effect_loader import (
    VisualEffectConfigLoader
)
from app.modules.video.config.loaders.fade_loader import (
    FadeConfigLoader
)
from app.modules.video.config.loaders.subtitle_loader import (
    SubtitleConfigLoader
)
from app.modules.video.config.loaders.validation_loader import (
    ValidationConfigLoader
)


@dataclass(frozen=True)
class VideoConfig:

    width: int
    height: int
    fps: int

    pixel_format: str

    subtitles: SubtitleConfig | None
    motion: MotionConfig
    transitions: TransitionConfig
    overlays: OverlayConfig
    visual_effects: VisualEffectConfig
    fade: FadeConfig
    validation: ValidationConfig

    codec: str
    preset: str
    crf: int

    audio_codec: str
    audio_bitrate: str

    movflags: str

    subtitle_cue_policy: dict | None = None

    @property
    def subtitle_offset(
        self
    ):
        if self.subtitles is None:
            return 0.0
        return self.subtitles.offset

    @property
    def subtitle_style(
        self
    ):
        if self.subtitles is None:
            return None
        style = {
            "font": self.subtitles.font,
            "font_size": self.subtitles.font_size,
            "bold": self.subtitles.bold,
            "primary_colour": self.subtitles.primary_colour,
            "outline_colour": self.subtitles.outline_colour,
            "back_colour": self.subtitles.back_colour,
            "border_style": self.subtitles.border_style,
            "outline": self.subtitles.outline,
            "shadow": self.subtitles.shadow,
            "alignment": self.subtitles.alignment,
            "margin_v": self.subtitles.margin_v,
            "offset": self.subtitles.offset
        }
        for field in (
            "italic",
            "underline",
            "strikeout",
            "secondary_colour",
            "margin_l",
            "margin_r",
            "scale_x",
            "scale_y",
            "spacing",
        ):
            value = getattr(self.subtitles, field)
            if value is not None:
                style[field] = value
        if self.subtitles.dynamic:
            style["dynamic"] = True
        return style


class VideoConfigLoader:

    def __init__(
        self,
        subtitle_profile,
        config_manager=None
    ):
        self.subtitle_profile = subtitle_profile
        self.config_manager = (
            config_manager
            or ConfigManager()
        )

    def load(
        self,
        render_subtitles=True,
    ):
        profile = (
            self.config_manager
            .get_profile_config()
        )

        if not isinstance(
            profile,
            dict
        ):
            raise TypeError(
                "El perfil de vídeo debe ser "
                "un diccionario."
            )

        video_style = require_mapping(
            profile,
            "video_style",
            "video_style"
        )

        video = require_mapping(
            profile,
            "video",
            "video"
        )

        audio = require_mapping(
            profile,
            "audio",
            "audio"
        )

        if not isinstance(
            video_style,
            dict
        ):
            raise TypeError(
                "La configuración video_style "
                "debe ser un diccionario."
            )

        if not isinstance(
            video,
            dict
        ):
            raise TypeError(
                "La configuración video "
                "debe ser un diccionario."
            )

        if not isinstance(
            audio,
            dict
        ):
            raise TypeError(
                "La configuración audio "
                "debe ser un diccionario."
            )

        motion_config = (
            MotionConfigLoader().load(
                profile
            )
        )

        transition_config = (
            TransitionConfigLoader().load(
                profile
            )
        )

        overlay_config = (
            OverlayConfigLoader().load(
                profile
            )
        )

        visual_effect_config = (
            VisualEffectConfigLoader().load(
                profile
            )
        )

        fade_config = (
            FadeConfigLoader().load(
                profile
            )
        )

        subtitle_config = None
        if render_subtitles:
            if self.subtitle_profile is None:
                raise ValueError(
                    "La renderización con subtítulos requiere "
                    "subtitle_profile."
                )
            subtitle_config = (
                SubtitleConfigLoader().load_render_style(
                    self.subtitle_profile.render_style
                )
            )

        validation_config = (
            ValidationConfigLoader().load(
                profile
            )
        )

        width = require_int(
            video_style,
            "width",
            "video_style.width"
        )

        height = require_int(
            video_style,
            "height",
            "video_style.height"
        )

        fps = require_int(
            video_style,
            "fps",
            "video_style.fps"
        )

        crf = require_int(
            video,
            "crf",
            "video.crf"
        )

        if width <= 0:
            raise ValueError(
                "El ancho del vídeo debe ser "
                "superior a cero."
            )

        if height <= 0:
            raise ValueError(
                "La altura del vídeo debe ser "
                "superior a cero."
            )

        if fps <= 0:
            raise ValueError(
                "Los FPS deben ser superiores "
                "a cero."
            )

        if crf < 0 or crf > 51:
            raise ValueError(
                "El CRF debe estar comprendido "
                "entre 0 y 51."
            )

        return VideoConfig(
            width=width,
            height=height,
            fps=fps,

            pixel_format=require_text(
                video,
                "pixel_format",
                "video.pixel_format"
            ),

            subtitles=subtitle_config,
            motion=motion_config,
            transitions=transition_config,
            overlays=overlay_config,
            visual_effects=visual_effect_config,
            fade=fade_config,
            validation=validation_config,

            codec=require_text(
                video,
                "codec",
                "video.codec"
            ),

            preset=require_text(
                video,
                "preset",
                "video.preset"
            ),

            crf=crf,

            audio_codec=require_text(
                audio,
                "codec",
                "audio.codec"
            ),

            audio_bitrate=require_text(
                audio,
                "bitrate",
                "audio.bitrate"
            ),

            movflags=require_text(
                video,
                "movflags",
                "video.movflags"
            ),

            subtitle_cue_policy=(
                dict(self.subtitle_profile.cue_policy)
                if render_subtitles and self.subtitle_profile is not None
                else None
            ),
        )
