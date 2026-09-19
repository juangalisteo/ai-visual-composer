from dataclasses import dataclass

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


class ImagePromptSystem:

    non_human_scene_policies = (
        (
            "architecture",
            (
                "architecture",
                "architectural",
                "building",
                "cathedral",
                "temple",
                "palace",
                "ruins",
                "cityscape",
                "interior",
                "corridor",
            ),
            (
                "Credible architectural scale, layered depth, structural material "
                "detail, disciplined composition, motivated light, atmospheric "
                "perspective, and believable inhabitable space; avoid flat generic "
                "backdrops"
            ),
        ),
        (
            "symbolic_object",
            (
                "relic",
                "artifact",
                "amulet",
                "chalice",
                "mask",
                "hourglass",
                "candle",
                "key",
                "ritual object",
            ),
            (
                "Make the declared object the clear focal point with intentional "
                "composition, focal light, resolved tactile materials, controlled "
                "detail, and clear visual hierarchy; avoid competing focal points"
            ),
        ),
        (
            "anatomical_scientific",
            (
                "brain",
                "neuron",
                "neural",
                "heart",
                "anatomy",
                "anatomical",
                "organ",
                "cell",
                "molecule",
                "dna",
                "scientific structure",
            ),
            (
                "Present the declared subject with convincing structure, readable "
                "volume, precise material or anatomical detail, refined texture, "
                "and sophisticated light; avoid deformed, generic, or chaotic forms"
            ),
        ),
        (
            "energy_abstract",
            (
                "energy",
                "electric",
                "electricity",
                "magnetic",
                "plasma",
                "light field",
                "abstract",
                "wave",
                "particles",
                "aura",
            ),
            (
                "Use controlled layered composition, sculpted light, restrained "
                "color, and readable depth for clean powerful abstraction; avoid "
                "chaos, oversaturation, harsh effects, and visual noise"
            ),
        ),
        (
            "symbolic_geometry",
            (
                "geometry",
                "geometric",
                "glyph",
                "mandala",
                "constellation",
                "symbol",
            ),
            (
                "Make declared geometry clear and legible through refined balance, "
                "visual hierarchy, disciplined proportions, and coherent spatial "
                "composition; avoid floating symbols, visual noise, and awkward arrangement"
            ),
        ),
    )

    human_subject_cues = (
        "person",
        "people",
        "man",
        "woman",
        "child",
        "scientist",
        "researcher",
        "historian",
        "team",
        "portrait",
        "persona",
        "personas",
        "hombre",
        "mujer",
        "nino",
        "nina",
        "cientifico",
        "investigadora",
        "historiador",
        "equipo",
        "retrato",
    )

    base_visual_identity = (
        "professional photorealism, grounded documentary aesthetic"
    )

    cinematic_operational_identity = (
        "coherent production design, cinematic light, balanced composition, "
        "atmospheric depth, sharp detail"
    )

    human_casting_policy = (
        "Use only described people; preserve declared age, appearance, cultural, "
        "historical, narrative, and continuity cues"
    )

    human_anatomy_policy = (
        "Natural anatomy, accurate hands, distinctive non-generic faces, realistic "
        "skin, believable proportions"
    )

    human_wardrobe_policy = (
        "Fully clothed, non-revealing, appropriate wardrobe; no sexualization"
    )

    no_extra_people_policy = (
        "No people or faces unless explicitly described"
    )

    cinematic_operational_restrictions = (
        "No text, logos, watermarks, or readable writing"
    )

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
        rules = self.operational_rules_for_prompt(
            positive_prompt
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
                self.base_visual_identity,
            ),
            self._rule(
                "identity.cinematic",
                "identity",
                90,
                True,
                ("always",),
                self.cinematic_operational_identity,
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
                        self.human_casting_policy,
                    ),
                    self._rule(
                        "casting.human.anatomy",
                        "casting",
                        100,
                        True,
                        ("human_subject",),
                        self.human_anatomy_policy,
                    ),
                    self._rule(
                        "safety.human.wardrobe",
                        "safety",
                        100,
                        True,
                        ("human_subject",),
                        self.human_wardrobe_policy,
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
                    self.no_extra_people_policy,
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
                self.cinematic_operational_restrictions,
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
        for category, cues, text in self.non_human_scene_policies:
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

        for _, cues, policy in self.non_human_scene_policies:
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
            for cue in self.human_subject_cues
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
