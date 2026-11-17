"""Selección compartida de activos intro/outro."""

from app.modules.video.intro_outro import (
    IntroOutroPlan,
    IntroOutroSelection,
)
from app.shared.operational_error import create_operational_error


class IntroOutroSelector:
    """Compone la selección de intro/outro sobre terminal y recursos."""

    def __init__(
        self,
        terminal,
        on_cancel,
        intro_outro_catalog,
        resource_selection,
    ):
        self._terminal = terminal
        self._on_cancel = on_cancel
        self._intro_outro_catalog = intro_outro_catalog
        self._resource_selection = resource_selection

    def _write(self, message, writer):
        (writer or self._terminal.write)(message)

    def _select(self, items, selector):
        if selector is not None:
            return selector(items)
        return self._terminal.select_from_list(items, self._on_cancel)

    def select_intro_outro(self, profile_format, writer=None, selector=None):
        modes = ("none", "intro", "outro", "both")
        self._write("\nINTRO / OUTRO\n", writer)
        self._write("1. NINGUNO", writer)
        self._write("2. SOLO INTRO", writer)
        self._write("3. SOLO OUTRO", writer)
        self._write("4. INTRO + OUTRO", writer)
        mode = self._select(modes, selector)
        if mode == "none":
            return None

        intro = None
        outro = None
        if mode in {"intro", "both"}:
            assets = self.require_assets(profile_format, "intro")
            intro = IntroOutroSelection(
                self.select_asset(assets, "INTRO", writer, selector),
                "intro",
            )
        if mode in {"outro", "both"}:
            assets = self.require_assets(profile_format, "outro")
            outro = IntroOutroSelection(
                self.select_asset(assets, "OUTRO", writer, selector),
                "outro",
            )
        return IntroOutroPlan(intro=intro, outro=outro)

    def select_studio_intro_outro(self, profile_key, writer=None, selector=None):
        return self.select_intro_outro(
            profile_key.format,
            writer=writer,
            selector=selector,
        )

    def require_assets(self, profile_format, position):
        assets = self._intro_outro_catalog.discover(profile_format, position)
        if not assets:
            raise create_operational_error(
                family="FILESYSTEM",
                user_message=(
                    "No hay archivos MP4 disponibles para "
                    f"{position.upper()} en assets/videos/intro_outro/"
                    f"{profile_format}/{position}/."
                ),
                recommended_action=(
                    "Pon al menos un vídeo .mp4 en esa carpeta "
                    "y vuelve a intentarlo."
                ),
                operation="Seleccionar INTRO / OUTRO",
            )
        return assets

    def select_asset(self, assets, position, writer=None, selector=None):
        return self._resource_selection.select_studio_input_candidate(
            f"SELECCIONAR {position}",
            assets,
            direct=False,
            writer=writer,
            selector=selector,
        )
