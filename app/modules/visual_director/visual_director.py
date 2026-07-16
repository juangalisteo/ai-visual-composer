from dataclasses import dataclass, field
import re

from app.modules.images.safe_visual_policy import SafeVisualPolicy


@dataclass(frozen=True)
class VisualDirectionContext:
    scene_text: str
    visual_idea: str
    duration: float
    scene_index: int
    scene_count: int
    orientation: str
    previous_directives: dict[str, str] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class DirectedPrompt:
    positive_prompt: str
    negative_prompt: str
    final_prompt: str
    directives: dict[str, str]


class VisualDirector:

    safe_visual_policy = SafeVisualPolicy()

    base_negative_prompt = (
        "no text, no letters, no words, no typography, "
        "no captions, no subtitles, no logos, no watermark, "
        "no readable signs, no readable screens, "
        "no handwritten text, no printed text, "
        "no cartoon, no anime, no illustration, "
        "no distorted anatomy, no cluttered composition, "
        "no waxy skin, no mannequin faces, no artificial people"
    )

    negative_prompt = (
        safe_visual_policy.merge_negative_prompt(
            base_negative_prompt
        )
    )

    stop_words = {
        "a",
        "an",
        "and",
        "as",
        "con",
        "de",
        "del",
        "el",
        "en",
        "for",
        "in",
        "la",
        "las",
        "los",
        "of",
        "on",
        "or",
        "para",
        "por",
        "que",
        "the",
        "to",
        "un",
        "una",
        "with",
        "y"
    }

    environments = {
        "natural environment": {
            "bosque",
            "forest",
            "mountain",
            "montana",
            "ocean",
            "sea",
            "mar",
            "river",
            "rio",
            "sky",
            "cielo",
            "desert",
            "valley"
        },
        "interior environment": {
            "home",
            "casa",
            "interior",
            "room",
            "habitacion",
            "office",
            "oficina",
            "studio",
            "workshop",
            "taller",
            "window",
            "ventana",
            "door",
            "puerta"
        },
        "urban environment": {
            "city",
            "ciudad",
            "street",
            "calle",
            "building",
            "edificio",
            "plaza",
            "station",
            "estacion"
        },
        "cosmic symbolic space": {
            "stars",
            "estrellas",
            "cosmic",
            "cosmico",
            "galaxy",
            "galaxia",
            "universe",
            "universo",
            "light",
            "luz"
        },
        "intimate interior space": {
            "mind",
            "mente",
            "silence",
            "silencio",
            "memory",
            "memoria",
            "heart",
            "corazon",
            "soul",
            "alma"
        }
    }

    emotions = {
        "calm contemplative mood": {
            "calm",
            "calma",
            "peace",
            "paz",
            "silence",
            "silencio",
            "serene",
            "sereno"
        },
        "hopeful expansive mood": {
            "hope",
            "esperanza",
            "light",
            "luz",
            "rise",
            "ascenso",
            "freedom",
            "libertad"
        },
        "tense dramatic mood": {
            "fear",
            "miedo",
            "dark",
            "oscuro",
            "shadow",
            "sombra",
            "storm",
            "tormenta"
        },
        "introspective emotional mood": {
            "doubt",
            "duda",
            "truth",
            "verdad",
            "awareness",
            "conciencia",
            "awakening",
            "despertar"
        }
    }

    shot_styles = (
        "wide establishing shot",
        "medium cinematic shot",
        "close emotional framing",
        "low angle perspective",
        "high angle observational view"
    )

    lens_styles = (
        "35mm cinematic lens language",
        "50mm natural perspective",
        "85mm portrait compression",
        "24mm environmental depth",
        "documentary lens realism"
    )

    compositions = (
        "layered foreground, midground and background",
        "strong leading lines toward the subject",
        "balanced asymmetrical composition",
        "clean central visual hierarchy",
        "deep perspective with atmospheric depth"
    )

    lighting_styles = (
        "soft directional key light",
        "golden volumetric lighting",
        "cool diffused ambient light",
        "dramatic contrast with controlled shadows",
        "gentle rim light separating the subject"
    )

    color_styles = (
        "natural cinematic color grade",
        "warm highlights with cool shadows",
        "muted documentary palette",
        "deep contrast with restrained saturation",
        "clean luminous color separation"
    )

    human_art_direction = (
        "human art direction, credible human presence, natural body "
        "language, balanced posture, believable anatomy, subtle facial "
        "expression, coherent gaze, realistic skin and hair, "
        "context-appropriate wardrobe with natural fabric behavior"
    )

    human_context_direction = (
        "identity, interaction and styling shaped by setting, action, "
        "light and emotional tone"
    )

    art_direction = (
        "editorial art direction, professional cinematography, cohesive "
        "light-space integration, refined production design"
    )

    def direct(
        self,
        context
    ):
        self._validate(
            context
        )

        scene_text = self._clean_text(
            context.scene_text
        )
        visual_idea = self._clean_text(
            context.visual_idea
        )
        orientation = self._orientation(
            context.orientation
        )
        keywords = self._keywords(
            f"{scene_text} {visual_idea}"
        )

        directives = {
            "subject": self._subject(
                visual_idea=visual_idea,
                keywords=keywords
            ),
            "environment": self._match_group(
                keywords=keywords,
                groups=self.environments,
                default="scene-defined environment"
            ),
            "emotion": self._match_group(
                keywords=keywords,
                groups=self.emotions,
                default="focused cinematic mood"
            ),
            "composition": self._select_varied(
                options=self.compositions,
                scene_index=context.scene_index,
                previous=context.previous_directives.get(
                    "composition"
                )
            ),
            "camera": self._select_varied(
                options=self.shot_styles,
                scene_index=context.scene_index,
                previous=context.previous_directives.get(
                    "camera"
                )
            ),
            "lens": self._select_varied(
                options=self.lens_styles,
                scene_index=context.scene_index,
                previous=context.previous_directives.get(
                    "lens"
                )
            ),
            "lighting": self._select_varied(
                options=self.lighting_styles,
                scene_index=context.scene_index,
                previous=context.previous_directives.get(
                    "lighting"
                )
            ),
            "color": self._select_varied(
                options=self.color_styles,
                scene_index=context.scene_index,
                previous=context.previous_directives.get(
                    "color"
                )
            ),
            "orientation": orientation,
            "human_art_direction": self._human_art_direction(
                combined_text=(
                    f"{scene_text} {visual_idea}"
                )
            ),
            "human_context_direction": self._human_context_direction(
                combined_text=(
                    f"{scene_text} {visual_idea}"
                )
            ),
            "art_direction": self.art_direction,
            "detail": "natural detail, sharp focal plane, tactile textures",
            "realism": "photoreal cinematic still"
        }

        positive_prompt = self._assemble_positive_prompt(
            visual_idea=visual_idea,
            scene_text=scene_text,
            directives=directives
        )

        final_prompt = (
            f"{positive_prompt}, "
            f"avoid: {self.negative_prompt}"
        )

        return DirectedPrompt(
            positive_prompt=positive_prompt,
            negative_prompt=self.negative_prompt,
            final_prompt=final_prompt,
            directives=directives
        )

    def _validate(
        self,
        context
    ):
        if context.scene_index <= 0:
            raise ValueError(
                "scene_index must be greater than zero."
            )

        if context.scene_count <= 0:
            raise ValueError(
                "scene_count must be greater than zero."
            )

        if context.scene_index > context.scene_count:
            raise ValueError(
                "scene_index cannot exceed scene_count."
            )

        if context.duration is not None and float(
            context.duration
        ) <= 0:
            raise ValueError(
                "duration must be greater than zero."
            )

        if not self._clean_text(
            context.visual_idea
        ):
            raise ValueError(
                "visual_idea cannot be empty."
            )

    def _clean_text(
        self,
        value
    ):
        return re.sub(
            r"\s+",
            " ",
            str(
                value
                or ""
            )
        ).strip()

    def _keywords(
        self,
        text
    ):
        words = re.findall(
            r"\w+",
            text.lower()
        )

        return tuple(
            word
            for word in words
            if (
                len(word) > 2
                and word not in self.stop_words
            )
        )

    def _subject(
        self,
        visual_idea,
        keywords
    ):
        if keywords:
            return (
                "primary subject staged with clear narrative purpose"
            )

        return (
            "primary subject staged from "
            f"{visual_idea}"
        )

    def _match_group(
        self,
        keywords,
        groups,
        default
    ):
        keyword_set = set(
            keywords
        )

        for label, values in groups.items():
            if keyword_set & values:
                return label

        return default

    def _orientation(
        self,
        orientation
    ):
        normalized = str(
            orientation
            or ""
        ).strip().lower()

        if normalized == "vertical":
            return (
                "vertical 9:16 mobile composition, "
                "subject safely centered, full body or main form "
                "kept inside frame, strong top-to-bottom depth"
            )

        return (
            "wide horizontal 16:9 cinematic composition, "
            "panoramic lateral depth, subject distributed with "
            "clear negative space"
        )

    def _select_varied(
        self,
        options,
        scene_index,
        previous
    ):
        if not options:
            return ""

        selected = options[
            (scene_index - 1)
            % len(options)
        ]

        if (
            previous
            and selected == previous
            and len(options) > 1
        ):
            selected = options[
                scene_index
                % len(options)
            ]

        return selected

    def _human_art_direction(
        self,
        combined_text
    ):
        if not self.safe_visual_policy.has_human_subject(
            combined_text
        ):
            return ""

        return self.human_art_direction

    def _human_context_direction(
        self,
        combined_text
    ):
        if not self.safe_visual_policy.has_human_subject(
            combined_text
        ):
            return ""

        return self.human_context_direction

    def _assemble_positive_prompt(
        self,
        visual_idea,
        scene_text,
        directives
    ):
        parts = [
            visual_idea,
            (
                "narrative context: "
                f"{scene_text}"
            ),
            directives["subject"],
            directives["environment"],
            directives["emotion"],
            directives["composition"],
            directives["camera"],
            directives["lens"],
            directives["lighting"],
            directives["color"],
            directives["orientation"],
            directives["human_art_direction"],
            directives["human_context_direction"],
            directives["art_direction"],
            directives["realism"],
            directives["detail"],
            (
                "clear visual storytelling, atmospheric depth"
            )
        ]

        combined_text = (
            f"{visual_idea} {scene_text} "
            f"{directives['subject']}"
        )

        if self.safe_visual_policy.has_human_subject(
            combined_text
        ):
            parts.append(
                self.safe_visual_policy.clothing_guidance
            )

        return ", ".join(
            self._dedupe(
                part
                for part in parts
                if part
            )
        )

    def _dedupe(
        self,
        parts
    ):
        seen = set()
        result = []

        for part in parts:
            key = part.strip().lower()

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                part
            )

        return result
