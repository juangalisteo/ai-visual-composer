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
                    "cue_policy.text_case inválido: "
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
        transformed = []
        cue_line = 0
        for line in content.splitlines(keepends=True):
            if not line.strip():
                cue_line = 0
                transformed.append(line)
                continue

            cue_line += 1
            if cue_line < 3:
                transformed.append(line)
                continue

            text = line.rstrip("\r\n")
            ending = line[len(text):]
            transformed.append(self.apply(text) + ending)
        return "".join(transformed)
