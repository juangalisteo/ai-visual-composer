"""Preparación de la ruta STUDIO específica de INTRO / OUTRO."""

from app.modules.video.intro_outro import (
    IntroOutroPlan,
    IntroOutroSelection,
)


class StudioIntroOutroRouteSelection:
    def __init__(self, input_service, resource_selection):
        self._input_service = input_service
        self._resource_selection = resource_selection

    @staticmethod
    def _write(message, writer):
        (writer or (lambda value: None))(message)

    @staticmethod
    def _select(items, selector):
        return selector(items)

    def select_plan(
        self,
        profile_key,
        require_assets,
        select_asset,
        writer=None,
        selector=None,
    ):
        source_paths = self._input_service.discover_sources()
        source_path = self._resource_selection.select_studio_input_candidate(
            "VIDEO",
            source_paths,
            direct=len(source_paths) == 1,
            writer=writer,
            selector=selector,
        )
        modes = ("intro", "outro", "both")
        self._write("\nINTRO / OUTRO\n", writer)
        self._write("1. SOLO INTRO", writer)
        self._write("2. SOLO OUTRO", writer)
        self._write("3. INTRO + OUTRO", writer)
        mode = self._select(modes, selector)

        intro = None
        outro = None
        if mode in {"intro", "both"}:
            assets = require_assets(profile_key.platform, "intro")
            intro = IntroOutroSelection(select_asset(assets, "INTRO"), "intro")
        if mode in {"outro", "both"}:
            assets = require_assets(profile_key.platform, "outro")
            outro = IntroOutroSelection(select_asset(assets, "OUTRO"), "outro")
        return self._input_service.create_plan(
            IntroOutroPlan(intro=intro, outro=outro),
            source_path=source_path,
        )
