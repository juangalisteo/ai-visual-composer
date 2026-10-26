from copy import deepcopy
import re

from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.policies.punctuation import reconcile_timing_text
from app.modules.subtitles.policies.text_case import TextCasePolicy


class SubtitleCueTransformer:

    def __init__(self, subtitle_profile, render_fps, model_registry=None):
        subtitle_config = deepcopy(
            subtitle_profile.cue_policy
        )
        render_fps = float(render_fps)
        if render_fps <= 0:
            raise ValueError(
                "La configuración video_style.fps debe ser "
                "superior a cero."
            )

        subtitle_config.setdefault("render_fps", render_fps)
        self.text_case = TextCasePolicy.from_cue_policy(subtitle_config)
        self.mode = CueModelRegistry.mode_from(subtitle_config)
        self.model_registry = model_registry or CueModelRegistry()
        self.model = self.model_registry.create(subtitle_config)

    def transform(self, content, timing=None, canonical_content=None):
        if not isinstance(content, str) or not content.strip():
            raise ValueError("El contenido SRT está vacío.")

        blocks = re.split(
            r"\n\s*\n",
            content.strip(),
        )
        transformed = "\n\n".join(
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
        return self.text_case.apply_srt_cues(transformed)
