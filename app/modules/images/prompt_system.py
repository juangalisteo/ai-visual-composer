class ImagePromptSystem:

    base_visual_identity = (
        "professional cinematic realism, grounded documentary aesthetic, "
        "natural believable appearance, coherent production design, "
        "professional visual quality"
    )

    cinematic_operational_identity = (
        "photorealistic film still, natural anatomy, accurate hands, "
        "coherent faces, stable character identity when repeated across scenes, "
        "preserve described face, age, hairstyle, body type and clothing across "
        "scene sequence, consistent wardrobe and setting, "
        "motivated cinematic lighting, balanced composition, atmospheric depth, "
        "sharp subject detail"
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
