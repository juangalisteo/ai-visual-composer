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
                "Non-human architectural direction: convey credible spatial "
                "scale, layered depth, structural material detail, disciplined "
                "composition, motivated cinematic light, atmospheric perspective, "
                "and a believable inhabitable space. Avoid flat backdrops, generic "
                "buildings, stock-image framing, and weak spatial hierarchy"
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
                "Non-human symbolic object direction: make the declared object "
                "the clear visual protagonist with elegant intentional composition, "
                "focal lighting, resolved tactile materials, controlled surrounding "
                "detail, and visual hierarchy. Avoid a lost object, flat lighting, "
                "random elements, and competing focal points"
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
                "Non-human scientific and anatomical direction: present the "
                "declared subject with clean convincing structure, readable volume, "
                "precise material or anatomical detail, refined texture, and "
                "sophisticated illumination. Avoid soft deformed forms, generic "
                "illustration, visual chaos, and poorly defined detail"
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
                "Non-human energy and abstraction direction: use controlled "
                "layered composition, intentional sculpted light, restrained color, "
                "and readable depth for powerful but clean abstract imagery. Avoid "
                "gratuitous chaos, oversaturation, harsh effects, and disordered "
                "visual noise"
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
                "Non-human symbolic geometry direction: make the declared symbol "
                "or geometry clear and legible through refined balance, visual "
                "hierarchy, disciplined proportions, and a coherent spatial "
                "composition. Avoid floating symbols without design, visual noise, "
                "awkward arrangement, and unrelated elements"
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
        "professional cinematic realism, grounded documentary aesthetic, "
        "natural believable appearance, coherent production design, "
        "professional visual quality"
    )

    cinematic_operational_identity = (
        "photorealistic film still, natural believable material detail, "
        "coherent production design, consistent setting, "
        "motivated cinematic lighting, balanced composition, atmospheric depth, "
        "sharp subject detail"
    )

    human_casting_policy = (
        "Do not add people, faces, or human figures unless the supplied visual "
        "scene explicitly requires them. When people are explicitly described, "
        "preserve only those people. Treat explicit geographic, cultural, "
        "historical, and narrative cues as primary casting direction; adapt "
        "appearance, facial variation, and clothing to those cues rather than "
        "replacing them with generic casting. When the visual context is "
        "clearly European, Mediterranean, or Western, favor naturally coherent "
        "casting for that context while preserving facial variation and avoiding "
        "stock-looking faces. Honor explicit Asian, African, Latin American, "
        "or other cultural context naturally; do not impose an unrelated default "
        "ethnicity. For a neutral context, use natural human variation and "
        "cinematic coherence within the narrative block; do not switch "
        "phenotypes arbitrarily scene by scene, make a single archetype "
        "dominant, or create unjustified heterogeneous mixing. Use available "
        "continuity cues to preserve coherent casting across related scenes, "
        "repeated characters, shared groups, eras, and environments. Use natural "
        "anatomy, accurate hands, distinctive facial structure, realistic skin "
        "texture, subtle imperfections, expressive eyes, believable proportions, "
        "and context-appropriate wardrobe. Avoid generic stock-looking faces, "
        "repetitive facial archetypes, identical-looking characters, artificial "
        "facial symmetry, plastic skin, flat expressions, arbitrary phenotype "
        "switching between related scenes, and repeated East Asian facial "
        "archetypes when unsupported by the scene context"
    )

    cinematic_operational_restrictions = (
        "fully clothed, context appropriate non revealing wardrobe, "
        "modest full coverage clothing, no exposed back, no bare shoulders, "
        "covered shoulders, covered back, high neckline, "
        "no plunging neckline, no crop top, no sexualization, "
        "blank pages, blank screens, blank boards, unmarked uniforms, "
        "unmarked signs, no badges with writing, "
        "no text, no letters, no words, no typography, "
        "no captions, no subtitles, no logos, no watermarks, "
        "no readable characters, no handwritten text, no printed text, "
        "no text on books, no text on screens, no text on walls, "
        "no text on objects, no text on signs, no text on uniforms, "
        "no readable badges, no writing on boards"
    )

    def compose_cinematic_backend_prompt(
        self,
        positive_prompt
    ):
        return ", ".join(
            self.dedupe_prompt_parts(
                (
                    positive_prompt,
                    self.base_visual_identity,
                    self.cinematic_operational_identity,
                    self.human_casting_policy,
                    self.non_human_visual_direction(
                        positive_prompt
                    ),
                    self.cinematic_operational_restrictions
                )
            )
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
