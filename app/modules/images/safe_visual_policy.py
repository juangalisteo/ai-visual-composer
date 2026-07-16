from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SafePromptResult:
    positive_prompt: str
    negative_prompt: str
    final_prompt: str
    applied: bool
    rewritten: bool
    human_subject: bool
    violations: tuple[str, ...]


class SafeVisualPolicy:

    clothing_guidance = (
        "fully clothed, elegant clothing, modest clothing, "
        "appropriate outfit, cinematic wardrobe, "
        "non-revealing clothing"
    )

    global_negative_terms = (
        "nudity",
        "nude",
        "naked",
        "topless",
        "bottomless",
        "bare breasts",
        "bare chest",
        "nipples",
        "genitals",
        "pubic",
        "transparent clothing",
        "see-through clothing",
        "lingerie",
        "underwear",
        "bikini",
        "micro bikini",
        "thong",
        "fetish",
        "erotic",
        "sexualized",
        "suggestive pose",
        "provocative",
        "nsfw",
        "porn",
        "explicit",
        "uncensored"
    )

    human_terms = (
        "adult",
        "boy",
        "character",
        "child",
        "couple",
        "crowd",
        "dancer",
        "face",
        "family",
        "father",
        "female",
        "figure",
        "girl",
        "hombre",
        "human",
        "kid",
        "lady",
        "male",
        "man",
        "men",
        "mother",
        "mujer",
        "niña",
        "niño",
        "people",
        "person",
        "persona",
        "portrait",
        "silhouette",
        "teen",
        "woman",
        "women"
    )

    unsafe_rewrites = {
        "transparent clothing": "opaque elegant clothing",
        "see-through clothing": "opaque elegant clothing",
        "micro bikini": "elegant modest outfit",
        "bare breasts": "modest covered chest",
        "bare chest": "modest covered chest",
        "suggestive pose": "natural cinematic pose",
        "sexualized": "non-sexual cinematic",
        "provocative": "composed cinematic",
        "bottomless": "fully clothed",
        "lingerie": "elegant wardrobe",
        "underwear": "appropriate outfit",
        "topless": "fully clothed",
        "bikini": "modest clothing",
        "thong": "modest clothing",
        "erotic": "non-sexual",
        "fetish": "cinematic",
        "naked": "fully clothed",
        "nudity": "fully clothed",
        "nude": "fully clothed",
        "nipples": "covered chest",
        "genitals": "covered body",
        "pubic": "covered body",
        "nsfw": "safe for work",
        "porn": "cinematic",
        "explicit": "safe for work",
        "uncensored": "safe for work"
    }

    def apply(
        self,
        positive_prompt,
        negative_prompt=""
    ):
        positive_prompt = self._clean_text(
            positive_prompt
        )
        negative_prompt = self._clean_text(
            negative_prompt
        )

        violations = self.find_violations(
            positive_prompt
        )
        rewritten_prompt = self._rewrite_prompt(
            positive_prompt
        )

        rewritten = (
            rewritten_prompt
            != positive_prompt
        )

        human_subject = (
            self.has_human_subject(
                rewritten_prompt
            )
            or self.has_human_subject(
                positive_prompt
            )
        )

        if human_subject:
            rewritten_prompt = self._append_once(
                text=rewritten_prompt,
                fragment=self.clothing_guidance
            )

        safe_negative = self.merge_negative_prompt(
            negative_prompt
        )

        final_prompt = (
            f"{rewritten_prompt}, avoid: {safe_negative}"
        )

        return SafePromptResult(
            positive_prompt=rewritten_prompt,
            negative_prompt=safe_negative,
            final_prompt=final_prompt,
            applied=True,
            rewritten=rewritten,
            human_subject=human_subject,
            violations=violations
        )

    def validate(
        self,
        prompt
    ):
        violations = self.find_violations(
            prompt
        )

        if violations:
            raise ValueError(
                "Unsafe visual prompt terms detected: "
                + ", ".join(
                    violations
                )
            )

    def find_violations(
        self,
        prompt
    ):
        lowered = self._normalized(
            prompt
        )

        return tuple(
            term
            for term in self.global_negative_terms
            if self._contains_term(
                lowered,
                term
            )
        )

    def has_human_subject(
        self,
        prompt
    ):
        lowered = self._normalized(
            prompt
        )

        return any(
            self._contains_term(
                lowered,
                term
            )
            for term in self.human_terms
        )

    def merge_negative_prompt(
        self,
        negative_prompt
    ):
        parts = [
            part.strip()
            for part in negative_prompt.split(
                ","
            )
            if part.strip()
        ]

        parts.extend(
            self.global_negative_terms
        )

        return ", ".join(
            self._dedupe(
                parts
            )
        )

    def _rewrite_prompt(
        self,
        prompt
    ):
        rewritten = prompt

        for unsafe, safe in sorted(
            self.unsafe_rewrites.items(),
            key=lambda item: len(
                item[0]
            ),
            reverse=True
        ):
            rewritten = re.sub(
                self._term_pattern(
                    unsafe
                ),
                safe,
                rewritten,
                flags=re.IGNORECASE
            )

        return self._clean_text(
            rewritten
        )

    def _append_once(
        self,
        text,
        fragment
    ):
        if fragment.lower() in text.lower():
            return text

        if not text:
            return fragment

        return (
            f"{text}, {fragment}"
        )

    def _dedupe(
        self,
        parts
    ):
        seen = set()
        result = []

        for part in parts:
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

    def _contains_term(
        self,
        normalized_prompt,
        term
    ):
        pattern = self._term_pattern(
            term
        )

        return re.search(
            pattern,
            normalized_prompt,
            flags=re.IGNORECASE
        ) is not None

    def _term_pattern(
        self,
        term
    ):
        words = re.escape(
            term
        ).replace(
            r"\ ",
            r"\s+"
        )

        return (
            r"(?<!\w)"
            + words
            + r"(?!\w)"
        )

    def _normalized(
        self,
        value
    ):
        return self._clean_text(
            value
        ).lower()

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
