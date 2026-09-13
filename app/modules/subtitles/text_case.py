VALID_TEXT_CASES = ("original", "uppercase", "lowercase")


class TextCasePolicy:
    """Apply one declared text-case policy to completed SRT cue text."""

    def __init__(self, mode):
        self.mode = mode

    @classmethod
    def from_cue_policy(cls, cue_policy):
        text_case = cue_policy.get("text_case")
        has_text_case = "text_case" in cue_policy
        uppercase = cue_policy.get("uppercase")
        has_uppercase = "uppercase" in cue_policy
        if has_text_case:
            if text_case not in VALID_TEXT_CASES:
                raise ValueError(
                    "cue_policy.text_case invalido: "
                    f"{text_case!r}. Valores permitidos: "
                    f"{', '.join(VALID_TEXT_CASES)}."
                )
        if has_uppercase and not isinstance(uppercase, bool):
            raise TypeError("cue_policy.uppercase debe ser booleana.")
        if has_text_case and has_uppercase:
            coherent = (
                (text_case == "uppercase" and uppercase)
                or (text_case == "original" and not uppercase)
            )
            if not coherent:
                raise ValueError(
                    "cue_policy.text_case y cue_policy.uppercase "
                    "son contradictorios."
                )
        if has_text_case:
            return cls(text_case)
        return cls("uppercase" if uppercase else "original")

    def apply(self, text):
        if self.mode == "uppercase":
            return text.upper()
        if self.mode == "lowercase":
            return text.lower()
        return text

    def apply_srt_cues(self, content):
        parts = content.split("\n\n")
        transformed = []
        for part in parts:
            lines = part.splitlines()
            if len(lines) >= 3:
                lines[2:] = [self.apply(line) for line in lines[2:]]
            transformed.append("\n".join(lines))
        return "\n\n".join(transformed)
