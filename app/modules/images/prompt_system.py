class ImagePromptSystem:

    base_visual_identity = (
        "professional cinematic realism, grounded documentary aesthetic, "
        "natural believable appearance, coherent production design, "
        "professional visual quality"
    )

    def build_legacy_prompt(
        self,
        visual_idea
    ):
        return (
            f"{visual_idea}, "
            "ultra realistic cinematic image, "
            "photorealistic, documentary style, "
            "golden volumetric lighting, "
            "deep shadows, natural colors, "
            "high detail, sharp focus, "
            "epic composition, atmospheric depth, "
            "no cartoon, no anime, no illustration, "
            "premium film still, 8k, "
            "no text, no letters, no words, "
            "no typography, no captions, "
            "no subtitles, no logos, "
            "no watermarks, no signs, "
            "no readable characters, "
            "no handwritten text, "
            "no printed text, "
            "no text on books, "
            "no text on screens, "
            "no text on walls, "
            "no text on objects"
        )

    def compose_backend_prompt(
        self,
        positive_prompt,
        negative_prompt=""
    ):
        prompt = ", ".join(
            self.dedupe_prompt_parts(
                (
                    positive_prompt,
                    self.base_visual_identity
                )
            )
        )

        if negative_prompt:
            prompt = (
                f"{prompt}, avoid: {negative_prompt}"
            )

        return prompt

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
