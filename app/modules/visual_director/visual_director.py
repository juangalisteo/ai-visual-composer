from dataclasses import dataclass, field
import re


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

    base_negative_prompt = (
        "no text, no letters, no words, no typography, "
        "no captions, no subtitles, no logos, no watermark, "
        "no readable signs, no readable screens, "
        "no handwritten text, no printed text, "
        "no cartoon, no anime, no illustration, "
        "no distorted forms, no cluttered composition"
    )

    negative_prompt = base_negative_prompt

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
        "urban environment": {
            "city",
            "ciudad",
            "street",
            "calle",
            "building",
            "edificio",
            "room",
            "habitacion",
            "window",
            "ventana",
            "door",
            "puerta"
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
                default="clear symbolic environment"
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
            "detail": "high detail, sharp focus, realistic textures",
            "realism": "photorealistic cinematic still"
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
                "main subject built around "
                + ", ".join(
                    keywords[:5]
                )
            )

        return (
            "main subject clearly derived from "
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
                "subject safely centered, main form "
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

    def _assemble_positive_prompt(
        self,
        visual_idea,
        scene_text,
        directives
    ):
        parts = [
            visual_idea,
            (
                "visual interpretation of the scene meaning: "
                f"{scene_text}"
            ),
            directives["subject"],
            directives["environment"],
            directives["emotion"],
            directives["composition"],
            directives["camera"],
            directives["lighting"],
            directives["color"],
            directives["orientation"],
            directives["realism"],
            directives["detail"],
            (
                "clear readable visual storytelling, "
                "professional art direction, atmospheric depth"
            )
        ]

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
