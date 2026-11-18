"""Selección compartida de recursos para rutas STUDIO."""

from app.shared.operational_error import create_missing_asset_error


class ResourceSelection:
    """Selecciona recursos sin apropiarse de servicios de dominio."""

    def __init__(self, terminal, on_cancel, studio_music_selector):
        self._terminal = terminal
        self._on_cancel = on_cancel
        self._studio_music_selector = studio_music_selector

    def _write(self, message, writer):
        (writer or self._terminal.write)(message)

    def _select(self, items, selector):
        if selector is not None:
            return selector(items)
        return self._terminal.select_from_list(items, self._on_cancel)

    def select_studio_input_candidate(
        self,
        label,
        candidates,
        direct,
        writer=None,
        selector=None,
    ):
        if direct:
            return candidates[0]

        self._write(f"\n{label}\n", writer)
        for index, candidate in enumerate(candidates, start=1):
            self._write(f"{index}. {candidate.name}", writer)
        return self._select(candidates, selector)

    def select_studio_music(self, writer=None, selector=None):
        self._write("\nMÚSICA\n", writer)
        self._write("1. Sí", writer)
        self._write("2. No", writer)
        if not self._select((True, False), selector):
            return None
        try:
            return self._studio_music_selector.select("random")
        except (FileNotFoundError, NotADirectoryError) as error:
            raise create_missing_asset_error(
                error, operation="Seleccionar música"
            ) from error
