"""Elegir opciones de menú por su etiqueta, no por su número.

Un test que contesta «2» elige lo que esté en segundo lugar: si el orden del
menú cambia, elige otra cosa sin avisar. ``MenuAnswers`` busca cada opción por
su etiqueta en el menú que se acaba de mostrar y falla si no está.
"""

import re

import pytest

_OPTION = re.compile(r"^\s*(\d+)\.\s(.*)$")


def option_number(menu_text, label):
    """Número (como texto) de la opción con esa etiqueta en el menú."""
    numbers = [
        match.group(1)
        for match in map(_OPTION.match, menu_text.splitlines())
        if match and match.group(2).strip() == label
    ]
    if len(numbers) != 1:
        raise AssertionError(
            f"La opción {label!r} aparece {len(numbers)} veces en el menú:\n"
            f"{menu_text}"
        )
    return numbers[0]


class Typed(str):
    """Respuesta que se escribe tal cual porque no es una opción de menú."""


class MenuAnswers:
    """Contesta cada pregunta con la opción de la siguiente etiqueta.

    Recoge lo que se muestra (``print``, ``write`` o el texto de ``screen``)
    y, en cada pregunta, busca la etiqueta en lo mostrado desde la pregunta
    anterior. Sirve como ``input``, como lector y escritor de ``Terminal``,
    como ``selector`` y como terminal falsa (``select_from_list``).
    """

    def __init__(self, *labels, screen=None):
        self._labels = list(labels)
        self._screen = screen
        self._seen = 0
        self._shown = []
        self.messages = []

    def write(self, message):
        self.messages.append(message)
        self._shown.append(f"{message}\n")

    def print(self, *args, sep=" ", end="\n", **_kwargs):
        self._shown.append(sep.join(str(arg) for arg in args) + end)

    def input(self, prompt=""):
        menu = self._take_shown()
        if not self._labels:
            raise AssertionError(f"Pregunta sin respuesta prevista:\n{menu}")
        label = self._labels.pop(0)
        if isinstance(label, Typed):
            return str(label)
        return option_number(menu, label)

    read = input

    def select(self, items):
        return items[int(self.input()) - 1]

    def select_from_list(self, items, on_cancel):
        return self.select(items)

    def _take_shown(self):
        if self._screen is not None:
            text = self._screen()
            shown, self._seen = text[self._seen:], len(text)
            return shown
        shown = "".join(self._shown)
        self._shown.clear()
        return shown


def test_menu_answers_choose_by_label_whatever_the_number():
    answers = MenuAnswers("Segunda", "Primera")
    answers.write("\nMENÚ\n")
    answers.write("1. Primera")
    answers.write("2. Segunda")
    assert answers.input() == "2"
    answers.print("\nMENÚ\n")
    answers.print("1. Segunda")
    answers.print("2. Primera")
    assert answers.select(("segunda", "primera")) == "primera"


def test_menu_answers_fail_when_the_label_is_missing_or_repeated():
    answers = MenuAnswers("Tercera", "Doble")
    answers.write("1. Primera")
    with pytest.raises(AssertionError, match="'Tercera' aparece 0 veces"):
        answers.input()
    answers.write("1. Doble")
    answers.write("2. Doble")
    with pytest.raises(AssertionError, match="'Doble' aparece 2 veces"):
        answers.input()
    assert MenuAnswers(Typed("texto libre")).input() == "texto libre"
    with pytest.raises(AssertionError, match="sin respuesta prevista"):
        MenuAnswers().input()
