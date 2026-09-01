class ImagePromptSystem:

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
        "preserve only those people and make their casting coherent with the "
        "stated geographic, cultural, historical, and narrative context. Honor "
        "explicit European or Mediterranean, Asian, African, Latin American, "
        "or other cultural context naturally; do not impose an unrelated default "
        "ethnicity. For a neutral context, use natural human variation without "
        "making a single phenotype dominant, while preserving coherence among "
        "people in the same scene. Use natural anatomy, accurate hands, "
        "distinctive facial structure, realistic skin texture, subtle "
        "imperfections, expressive eyes, believable proportions, and "
        "context-appropriate wardrobe. Avoid generic stock-looking faces, "
        "repetitive facial archetypes, identical-looking characters across "
        "scenes, overly symmetrical AI faces, plastic skin, flat expressions, "
        "and repeated East Asian facial archetypes when unsupported by the "
        "scene context"
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
                    self.cinematic_operational_restrictions
                )
            )
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
