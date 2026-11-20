"""Scene prompt written from a template: whole sentences, said once, no letters.

The fragment compiler of ``PromptTranslator`` splits every field at its commas
and cuts it by words to fit a budget; a description such as
``filmable_interpretation`` comes out in pieces and repeated by the other
fields. A ``ScenePromptTemplate`` instead names which fields of the brief
make the scene part of the prompt (``{filmable_interpretation}``…) and how
they are joined. Composing it:

- keeps each value whole (only the end punctuation goes);
- drops a value, or an item of a list, already said by another one, so the
  subject is not repeated;
- replaces the objects that would make the image model draw letters (an open
  book, a newspaper…) by the visual replacement declared for them;
- removes the separators left by empty values.

It never shortens a value: a scene over budget is an error, not a cut.
"""

import re
from dataclasses import dataclass, field


# Fields of the brief copied as they are from the storyboard scene.
SCENE_TEMPLATE_FIELDS = (
    "visible_subject",
    "visible_action",
    "visible_environment",
    "time_context",
    "key_objects",
    "spatial_relationships",
    "filmable_interpretation",
    "visual_constraints",
)

_MARKER = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
_END_PUNCTUATION = " \t\n.,;:"
_VOWELS = "aeiou"


@dataclass(frozen=True)
class ScenePromptTemplate:
    """Template of the scene part of the prompt and its letter-free objects.

    ``text_free_objects`` holds ``(phrase, replacement)`` pairs, applied in
    order; each phrase is matched as whole words and in any case.
    """

    template: str
    text_free_objects: tuple[tuple[str, str], ...] = field(
        default_factory=tuple
    )

    def __post_init__(self):
        if not str(self.template or "").strip():
            raise ValueError("The scene template is empty.")
        unknown = [
            name
            for name in self.fields
            if name not in SCENE_TEMPLATE_FIELDS
        ]
        if unknown:
            raise ValueError(
                f"Unknown scene template field: {unknown[0]}."
            )
        if not self.fields:
            raise ValueError("The scene template names no field.")

    @property
    def fields(self) -> tuple[str, ...]:
        """Fields named by the template, in order and once."""
        return tuple(dict.fromkeys(_MARKER.findall(self.template)))


@dataclass(frozen=True)
class ScenePromptComposition:
    prompt: str
    # (field, text) of each field that reached the prompt.
    values: tuple[tuple[str, str], ...]
    # (field, text) dropped because another value already says it.
    repeated: tuple[tuple[str, str], ...]
    # (found, replacement) of each object with letters that was replaced.
    replaced_objects: tuple[tuple[str, str], ...]


def compose_scene_prompt(template, values) -> ScenePromptComposition:
    """Scene prompt of ``template`` with the brief ``values`` (field → value)."""
    replaced_objects = []
    units = []
    for name in template.fields:
        for item in _items(values.get(name)):
            text, replaced = _replace_text_objects(
                item,
                template.text_free_objects,
            )
            replaced_objects.extend(replaced)
            if text:
                units.append((name, text))

    kept, repeated = _without_repetitions(units)
    rendered = _MARKER.sub(
        lambda match: ", ".join(
            text
            for name, text in kept
            if name == match.group(1)
        ),
        template.template,
    )
    return ScenePromptComposition(
        prompt=_clean_separators(rendered),
        values=tuple(kept),
        repeated=tuple(repeated),
        replaced_objects=tuple(replaced_objects),
    )


def _items(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        raw = value
    else:
        raw = (value,)
    items = []
    for item in raw:
        text = " ".join(str(item or "").split()).strip(_END_PUNCTUATION)
        if text:
            items.append(text)
    return tuple(items)


def _replace_text_objects(text, text_free_objects):
    replaced = []
    for phrase, replacement in text_free_objects:
        words = r"\s+".join(re.escape(word) for word in phrase.split())
        pattern = re.compile(
            rf"(?<!\w)(?:(?P<article>an?)\s+)?(?P<phrase>{words})(?!\w)",
            re.IGNORECASE,
        )

        def substitute(match, replacement=replacement):
            found = match.group(0)
            article = match.group("article")
            result = replacement
            if article:
                new_article = (
                    "an" if replacement[:1].lower() in _VOWELS else "a"
                )
                if article[0].isupper():
                    new_article = new_article.capitalize()
                result = f"{new_article} {replacement}"
            elif match.group("phrase")[0].isupper():
                result = replacement[:1].upper() + replacement[1:]
            replaced.append((found, result))
            return result

        text = pattern.sub(substitute, text)
    return text, replaced


def _without_repetitions(units):
    """Drop each unit whose words are already inside another unit."""
    kept = []
    repeated = []
    keys = [_key(text) for _, text in units]
    for index, (name, text) in enumerate(units):
        key = keys[index]
        said_elsewhere = any(
            other != index
            and _contains(keys[other], key)
            and (len(keys[other]) > len(key) or other < index)
            for other in range(len(units))
        )
        if said_elsewhere:
            repeated.append((name, text))
        else:
            kept.append((name, text))
    return kept, repeated


def _key(text):
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _contains(container, part):
    return bool(part) and re.search(
        rf"(?<!\w){re.escape(part)}(?:e?s)?(?!\w)",
        container,
    ) is not None


def _clean_separators(text):
    text = " ".join(text.split())
    text = re.sub(r"\s+([,;.])", r"\1", text)
    text = re.sub(r"([,;])(?:\s*[,;])+", r"\1", text)
    return text.strip(" ,;")
