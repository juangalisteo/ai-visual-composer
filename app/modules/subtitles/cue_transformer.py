from copy import deepcopy
import re

from app.modules.subtitles.models.single_line_model import (
    SingleLineModel,
)
from app.modules.subtitles.models.word_by_word_model import (
    WordByWordModel,
)
from app.modules.subtitles.punctuation import reconcile_timing_text
from app.shared.config_contract import require_text


class SubtitleCueTransformer:

    def __init__(self, subtitle_profile, render_fps):
        subtitle_config = deepcopy(
            subtitle_profile.cue_policy
        )
        render_fps = float(render_fps)
        if render_fps <= 0:
            raise ValueError(
                "La configuracion video_style.fps debe ser "
                "superior a cero."
            )

        subtitle_config.setdefault("render_fps", render_fps)
        mode = require_text(
            subtitle_config,
            "mode",
            "cue_policy.mode",
        )

        if mode == "single_line":
            self.model = SingleLineModel(subtitle_config)
        elif mode == "word_by_word":
            self.model = WordByWordModel(subtitle_config)
        else:
            raise ValueError(
                "Modelo de subtitulos no soportado: "
                f"{mode}"
            )

    def transform(self, content, timing=None, canonical_content=None):
        if not isinstance(content, str) or not content.strip():
            raise ValueError("El contenido SRT esta vacio.")

        blocks = re.split(
            r"\n\s*\n",
            content.strip(),
        )
        return "\n\n".join(
            self.model.optimize(
                blocks,
                timing=reconcile_timing_text(
                    canonical_content
                    if canonical_content is not None
                    else content,
                    timing,
                    authoritative=canonical_content is not None,
                ),
            )
        )
