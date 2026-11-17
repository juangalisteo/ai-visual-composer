VALID_TEXT_CASES = ("original", "uppercase", "lowercase")


class TextCasePolicy:
    """Apply one declared text-case policy to completed SRT cue text."""

    def __init__(self, mode):
        self.mode = mode

    @classmethod
    def from_cue_policy(cls, cue_policy):
        if "uppercase" in cue_policy:
            raise ValueError(
                "cue_policy no admite la clave antigua uppercase. "
                "Use cue_policy.text_case."
            )
        if "text_case" not in cue_policy:
            return cls("original")
        text_case = cue_policy["text_case"]
        if text_case not in VALID_TEXT_CASES:
            raise ValueError(
                "cue_policy.text_case inválido: "
                f"{text_case!r}. Valores permitidos: "
                f"{', '.join(VALID_TEXT_CASES)}."
            )
        return cls(text_case)

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
