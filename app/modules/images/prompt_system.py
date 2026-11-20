import re
from dataclasses import dataclass, replace

from app.shared.prompt_library import (
    PromptLibrary,
    require_prompt_text,
    require_prompt_texts,
)
from app.shared.prompt_metrics import (
    estimate_conservative_tokens,
)


@dataclass(frozen=True)
class OperationalPromptRule:
    id: str
    category: str
    priority: int
    protected: bool
    conditions: tuple[str, ...]
    source: str
    text: str

    @property
    def estimated_token_cost(
        self,
    ) -> int:
        return estimate_conservative_tokens(
            self.text
        )


@dataclass(frozen=True)
class OperationalPromptComposition:
    prompt: str
    parts: tuple[tuple[str, str], ...]
    rules: tuple[OperationalPromptRule, ...] = ()


# Files of prompts/ with the fixed texts of every image prompt.
IMAGE_RULES = "image/rules.json"
# Visual identity: one file per tone or the shared default.
IMAGE_IDENTITY = "image/identity"


@dataclass(frozen=True)
class ImagePromptTexts:
    """Fixed texts joined to every image prompt, read from prompts/image/."""

    base_visual_identity: str
    cinematic_operational_identity: str
    human_subject_cues: tuple[str, ...]
    human_casting_policy: str
    human_anatomy_policy: str
    human_wardrobe_policy: str
    no_extra_people_policy: str
    cinematic_operational_restrictions: str
    # (category, cues, text) in order: the first category whose cue appears wins.
    non_human_scene_policies: tuple[tuple[str, tuple[str, ...], str], ...]

    @classmethod
    def load(cls, prompts=None, tone=None):
        prompts = prompts or PromptLibrary()
        identity_path = prompts.tone_file(
            IMAGE_IDENTITY,
            tone,
            suffix=".json",
        )
        identity = prompts.mapping(identity_path)
        rules = prompts.mapping(IMAGE_RULES)

        def text(document, path, key):
            return require_prompt_text(document, key, prompts, path)

        return cls(
            base_visual_identity=text(identity, identity_path, "base_visual"),
            cinematic_operational_identity=text(
                identity, identity_path, "cinematic"
            ),
            human_subject_cues=require_prompt_texts(
                rules, "human_subject_cues", prompts, IMAGE_RULES
            ),
            human_casting_policy=text(rules, IMAGE_RULES, "human_casting"),
            human_anatomy_policy=text(rules, IMAGE_RULES, "human_anatomy"),
            human_wardrobe_policy=text(rules, IMAGE_RULES, "human_wardrobe"),
            no_extra_people_policy=text(rules, IMAGE_RULES, "no_extra_people"),
            cinematic_operational_restrictions=text(
                rules, IMAGE_RULES, "no_text"
            ),
            non_human_scene_policies=_non_human_scene_policies(
                rules, prompts
            ),
        )


def _non_human_scene_policies(rules, prompts):
    directions = rules.get("non_human_directions")
    if not isinstance(directions, list) or not directions:
        require_prompt_texts(
            rules, "non_human_directions", prompts, IMAGE_RULES
        )
    policies = []
    for direction in directions:
        if not isinstance(direction, dict):
            direction = {}
        policies.append(
            (
                require_prompt_text(
                    direction, "category", prompts, IMAGE_RULES
                ),
                require_prompt_texts(
                    direction, "cues", prompts, IMAGE_RULES
                ),
                require_prompt_text(
                    direction, "text", prompts, IMAGE_RULES
                ),
            )
        )
    return tuple(policies)


class ImagePromptSystem:
    """Joins to each image prompt the visual identity and the rules.

    The texts come from prompts/image/ (``ImagePromptTexts``); they are read
    the first time they are needed, with the identity of ``tone``.
    """

    def __init__(
        self,
        texts=None,
        *,
        tone=None,
        prompts=None,
    ):
        self._texts = texts
        self._tone = tone
        self._prompts = prompts

    @property
    def texts(self) -> ImagePromptTexts:
        if self._texts is None:
            self._texts = ImagePromptTexts.load(
                self._prompts,
                self._tone,
            )
        return self._texts

    def compose_cinematic_backend_prompt(
        self,
        positive_prompt
    ):
        return self.compose_cinematic_backend_prompt_with_parts(
            positive_prompt
        ).prompt

    def compose_cinematic_backend_prompt_with_parts(
        self,
        positive_prompt
    ):
        rules = tuple(
            rule
            for rule in (
                self._without_what_the_scene_says(
                    rule,
                    positive_prompt,
                )
                for rule in self.operational_rules_for_prompt(
                    positive_prompt
                )
            )
            if rule is not None
        )
        parts = self._dedupe_labeled_prompt_parts(
            (
                (
                    "compiled_prompt",
                    positive_prompt,
                ),
                *(
                    (
                        rule.id,
                        rule.text,
                    )
                    for rule in rules
                ),
            )
        )
        return OperationalPromptComposition(
            prompt=", ".join(
                part
                for _, part in parts
            ),
            parts=parts,
            rules=rules,
        )

    def _without_what_the_scene_says(
        self,
        rule,
        positive_prompt,
    ):
        """Identity rule without the comma-separated parts the scene already says.

        "cinematic light" is not added again to a scene lit by cinematic
        light; an identity left with nothing is dropped.
        """
        if rule.category != "identity":
            return rule
        scene = _comparable(
            positive_prompt
        )
        fragments = tuple(
            fragment.strip()
            for fragment in rule.text.split(",")
            if fragment.strip()
        )
        kept = tuple(
            fragment
            for fragment in fragments
            if not _says(
                scene,
                _comparable(fragment),
            )
        )
        if len(kept) == len(fragments):
            return rule
        if not kept:
            return None
        return replace(
            rule,
            text=", ".join(kept),
        )

    def operational_rules_for_prompt(
        self,
        positive_prompt,
    ) -> tuple[OperationalPromptRule, ...]:
        human_subject = self._contains_human_subject(
            str(
                positive_prompt
                or ""
            ).lower()
        )
        rules = [
            self._rule(
                "identity.base_visual",
                "identity",
                90,
                True,
                ("always",),
                self.texts.base_visual_identity,
            ),
            self._rule(
                "identity.cinematic",
                "identity",
                90,
                True,
                ("always",),
                self.texts.cinematic_operational_identity,
            ),
        ]
        if human_subject:
            rules.extend(
                (
                    self._rule(
                        "casting.human.subject",
                        "casting",
                        100,
                        True,
                        ("human_subject",),
                        self.texts.human_casting_policy,
                    ),
                    self._rule(
                        "casting.human.anatomy",
                        "casting",
                        100,
                        True,
                        ("human_subject",),
                        self.texts.human_anatomy_policy,
                    ),
                    self._rule(
                        "safety.human.wardrobe",
                        "safety",
                        100,
                        True,
                        ("human_subject",),
                        self.texts.human_wardrobe_policy,
                    ),
                )
            )
        else:
            rules.append(
                self._rule(
                    "casting.non_human.no_extra_people",
                    "casting",
                    100,
                    True,
                    ("non_human_subject",),
                    self.texts.no_extra_people_policy,
                )
            )
            direction_rule = self._non_human_direction_rule(
                positive_prompt
            )
            if direction_rule is not None:
                rules.append(
                    direction_rule
                )
        rules.append(
            self._rule(
                "safety.no_text",
                "safety",
                100,
                True,
                ("always",),
                self.texts.cinematic_operational_restrictions,
            )
        )
        return tuple(
            rules
        )

    def _non_human_direction_rule(
        self,
        positive_prompt,
    ) -> OperationalPromptRule | None:
        prompt = str(
            positive_prompt
            or ""
        ).lower()
        for category, cues, text in self.texts.non_human_scene_policies:
            if self._contains_any(
                prompt,
                cues,
            ):
                return self._rule(
                    f"direction.non_human.{category}",
                    "direction",
                    88,
                    True,
                    (
                        "non_human_subject",
                        f"non_human_category:{category}",
                    ),
                    text,
                )
        return None

    def _rule(
        self,
        rule_id,
        category,
        priority,
        protected,
        conditions,
        text,
    ) -> OperationalPromptRule:
        return OperationalPromptRule(
            id=rule_id,
            category=category,
            priority=priority,
            protected=protected,
            conditions=conditions,
            source="ImagePromptSystem",
            text=text,
        )

    def _dedupe_labeled_prompt_parts(
        self,
        parts
    ):
        seen = set()
        result = []

        for category, part in parts:
            part = str(
                part
                or ""
            ).strip()

            if not part:
                continue

            key = part.lower()

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                (
                    category,
                    part,
                )
            )

        return tuple(
            result
        )

    def non_human_visual_direction(
        self,
        positive_prompt
    ):
        prompt = str(
            positive_prompt
            or ""
        ).lower()

        if self._contains_human_subject(prompt):
            return ""

        for _, cues, policy in self.texts.non_human_scene_policies:
            if self._contains_any(
                prompt,
                cues
            ):
                return policy

        return ""

    def _contains_any(
        self,
        value,
        cues
    ):
        return any(
            cue in value
            for cue in cues
        )

    def _contains_human_subject(
        self,
        value
    ):
        normalized = "".join(
            character
            if character.isalnum()
            else " "
            for character in value
        )
        padded = f" {normalized} "

        return any(
            f" {cue} " in padded
            for cue in self.texts.human_subject_cues
        )

    def dedupe_prompt_parts(
        self,
        parts
    ):
        seen = set()
        result = []

        for part in parts:
            part = str(
                part
                or ""
            ).strip()

            if not part:
                continue

            key = part.lower()

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                part
            )

        return result


def _comparable(text):
    """Lowercase words without punctuation, to compare what two texts say."""
    return " ".join(
        re.sub(
            r"[^\w\s]",
            " ",
            str(text or "").lower(),
        ).split()
    )


def _says(text, part):
    return bool(part) and re.search(
        rf"(?<!\w){re.escape(part)}(?:e?s)?(?!\w)",
        text,
    ) is not None
