import sys
from pathlib import Path

from app.shared.progress_logger import ProgressLogger
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_resolver import (
    SubtitleProfileResolver,
)
from app.modules.video.intro_outro import (
    IntroOutroCatalog,
    IntroOutroPlan,
    IntroOutroSelection,
)
from app.modules.audio.music_selector import MusicSelector


class RunController:

    def __init__(
        self,
        profile_resolver=None,
        subtitle_profile_resolver=None,
        intro_outro_catalog=None,
        studio_music_selector=None,
    ):
        self.profile_resolver = (
            profile_resolver
            or ProfileResolver()
        )
        self.intro_outro_catalog = (
            intro_outro_catalog
            or IntroOutroCatalog()
        )
        self.subtitle_profile_resolver = (
            subtitle_profile_resolver
            or SubtitleProfileResolver()
        )
        self.studio_music_selector = (
            studio_music_selector
            or MusicSelector()
        )

    def run(self):
        visual_pipeline = self.select_visual_pipeline()
        script_source = "generated"
        design_target = ""

        if visual_pipeline == "script":
            script_source = "manual"
            visual_pipeline = self.select_script_destination()
            if visual_pipeline == "design":
                script_source = "manual_design"
                design_target = self.select_design_target()
                visual_pipeline = design_target

        if visual_pipeline == "studio":
            return self._run_studio()

        if script_source == "manual_design":
            pipeline_mode = f"design_{design_target}"
        else:
            pipeline_mode = self.select_pipeline_mode()

        profile = self.select_profile(
            self._profile_scope(
                script_source=script_source,
                visual_pipeline=visual_pipeline,
                design_target=design_target
            )
        )
        subtitle_config = ""
        voice_config = ""
        music_category = None
        overlays_mode = "off"
        intro_outro_selection = None

        if pipeline_mode in {
            "full",
            "subtitles",
            "storyboard"
        }:
            subtitle_config = self.select_subtitle_config()

        if pipeline_mode not in {
            "script",
            "design_image",
            "design_video"
        }:
            voice_config = self.select_voice_config()
            music_category = self.select_music_category()

        if pipeline_mode == "full":
            overlays_mode = self.select_overlays_mode()

        if (
            pipeline_mode == "full"
            and visual_pipeline == "video"
        ):
            intro_outro_selection = (
                self.select_intro_outro()
            )

        project_name = self.ask_project_name()
        clear_output = self.ask_clear_output()
        profile_key = profile.get(
            "profile_key"
        )

        return {
            "visual_pipeline": visual_pipeline,
            "script_source": script_source,
            "design_target": design_target,
            "pipeline_mode": pipeline_mode,
            "profile_component": (
                profile_key.component.value
                if profile_key
                else ""
            ),
            "profile_platform": (
                profile_key.platform.value
                if profile_key
                else ""
            ),
            "profile_id": (
                profile_key.profile_id
                if profile_key
                else ""
            ),
            "subtitle_config": subtitle_config,
            "voice_config": voice_config,
            "music_category": music_category,
            "overlays_mode": overlays_mode,
            "intro_outro_selection": intro_outro_selection,
            "project_name": project_name,
            "clear_output": clear_output
        }

    def select_visual_pipeline(self):
        pipelines = [
            {
                "name": "Guion",
                "pipeline": "script"
            },
            {
                "name": "Imagen",
                "pipeline": "image"
            },
            {
                "name": "Video",
                "pipeline": "video"
            },
            {
                "name": "Studio",
                "pipeline": "studio"
            }
        ]

        self._print("\nAI VISUAL COMPOSER\n")

        for i, pipeline in enumerate(
            pipelines,
            start=1
        ):
            self._print(
                f"{i}. {pipeline['name']}"
            )

        while True:
            selected = self._select_from_list(
                pipelines
            )

            if selected.get(
                "available",
                True
            ):
                return selected[
                    "pipeline"
                ]

            self._print(
                "\nNo disponible."
            )

    def select_script_destination(self):
        destinations = [
            {
                "name": "Imagen",
                "pipeline": "image"
            },
            {
                "name": "Video",
                "pipeline": "video"
            },
            {
                "name": "Diseño",
                "pipeline": "design"
            }
        ]

        self._print("\nDESTINO\n")

        for i, destination in enumerate(
            destinations,
            start=1
        ):
            self._print(
                f"{i}. {destination['name']}"
            )

        while True:
            selected = self._select_from_list(
                destinations
            )

            if selected.get(
                "available",
                True
            ):
                return selected[
                    "pipeline"
                ]

            self._print(
                "\nNo disponible."
            )

    def select_design_target(self):
        targets = [
            {
                "name": "Imagen",
                "pipeline": "image"
            },
            {
                "name": "Video",
                "pipeline": "video"
            }
        ]

        self._print("\nDISEÑO\n")

        for i, target in enumerate(
            targets,
            start=1
        ):
            self._print(
                f"{i}. {target['name']}"
            )

        selected = self._select_from_list(
            targets
        )

        if not selected.get(
            "available",
            True
        ):
            self._print(
                "\nNo disponible."
            )
            sys.exit(0)

        return selected[
            "pipeline"
        ]

    def select_pipeline_mode(self):
        modes = [
            {
                "name": "Proyecto completo",
                "mode": "full"
            },
            {
                "name": "Solo audio",
                "mode": "audio"
            },
            {
                "name": "Audio + subtítulos",
                "mode": "subtitles"
            },
            {
                "name": "Audio + subtítulos + storyboard",
                "mode": "storyboard"
            }
        ]

        self._print("\nMODO\n")

        for i, mode in enumerate(
            modes,
            start=1
        ):
            self._print(
                f"{i}. {mode['name']}"
            )

        selected = self._select_from_list(
            modes
        )

        return selected["mode"]

    def select_profile(
        self,
        visual_pipeline="image"
    ):
        profiles = []

        if visual_pipeline == "script":
            for platform in ProfilePlatform:
                profile_key = ProfileKey.for_component(
                    ProfileComponent.GUION,
                    platform
                )
                profile = self.profile_resolver.resolve(
                    profile_key
                )
                profiles.append({
                    "platform": "guion",
                    "profile": platform.value,
                    "path": profile,
                    "profile_key": profile_key,
                })
        elif visual_pipeline == "design_image":
            for platform in ProfilePlatform:
                profile_key = ProfileKey.for_component(
                    ProfileComponent.IMAGEN,
                    platform
                )
                profile = self.profile_resolver.resolve(
                    profile_key
                )
                profiles.append({
                    "platform": "diseno",
                    "profile": platform.value,
                    "path": profile,
                    "profile_key": profile_key,
                })
        elif visual_pipeline == "design_video":
            for platform in ProfilePlatform:
                profile_key = ProfileKey.for_component(
                    ProfileComponent.VIDEO,
                    platform
                )
                profile = self.profile_resolver.resolve(
                    profile_key
                )
                profiles.append({
                    "platform": "diseno",
                    "profile": platform.value,
                    "path": profile,
                    "profile_key": profile_key,
                })
        else:
            components = {
                "image": ProfileComponent.IMAGEN,
                "video": ProfileComponent.VIDEO,
                "studio": ProfileComponent.STUDIO,
            }
            if visual_pipeline not in components:
                raise ValueError(
                    "Ámbito de perfil no soportado: "
                    f"{visual_pipeline}"
                )

            for platform in ProfilePlatform:
                component = components[visual_pipeline]
                profile_key = ProfileKey.for_component(
                    component,
                    platform
                )
                profile = self.profile_resolver.resolve(
                    profile_key
                )
                profiles.append({
                    "platform": (
                        "studio"
                        if component is ProfileComponent.STUDIO
                        else platform.value
                    ),
                    "profile": (
                        platform.value
                        if component is ProfileComponent.STUDIO
                        else "modo_conciencia"
                    ),
                    "path": profile,
                    "profile_key": profile_key,
                })

        if not profiles:
            raise FileNotFoundError(
                "No se encontraron perfiles "
                "en config/profiles."
            )

        self._print("\nPERFIL\n")

        for i, item in enumerate(
            profiles,
            start=1
        ):
            if item["platform"] in {
                "guion",
                "diseno",
                "studio",
            }:
                label = self._label(
                    item["profile"]
                )
            else:
                label = (
                    f"{self._label(item['platform'])} / "
                    f"{self._label(item['profile'])}"
                )

            self._print(
                f"{i}. {label}"
            )

        return self._select_from_list(
            profiles
        )

    def select_subtitle_config(self):
        configs = (
            "single_line",
            "word_by_word",
        )

        self._print(
            "\nSUBTÍTULOS\n"
        )

        for i, config in enumerate(
            configs,
            start=1
        ):
            self._print(
                f"{i}. "
                f"{self._subtitle_label(config)}"
            )

        selected = self._select_from_list(
            configs
        )

        return selected

    def select_studio_subtitle_config(self, profile_key):
        configs = self.subtitle_profile_resolver.discover_styles(
            profile_key
        )

        self._print("\nSUBTITULOS\n")
        for index, config in enumerate(configs, start=1):
            self._print(
                f"{index}. {self._subtitle_label(config)}"
            )

        return self._select_from_list(configs)

    def select_studio_light_leaks(self):
        self._print("\n¿UTILIZAR LIGHT LEAKS?\n")
        self._print("1. NO")
        self._print("2. SÍ")
        return self._select_from_list((False, True))

    def select_studio_music(self):
        self._print("\n¿UTILIZAR MÚSICA?\n")
        self._print("1. NO")
        self._print("2. SÍ")
        enabled = self._select_from_list((False, True))
        if not enabled:
            return None

        tracks = self.studio_music_selector.discover_tracks()
        self._print("\nMÚSICA\n")
        for index, track in enumerate(tracks, start=1):
            try:
                label = track.relative_to(
                    self.studio_music_selector.music_path
                )
            except ValueError:
                label = track.name
            self._print(f"{index}. {label}")
        return self._select_from_list(tracks)

    def select_studio_intro_outro(self):
        modes = ("none", "intro", "outro", "both")
        self._print("\nINTRO / OUTRO\n")
        self._print("1. NINGUNO")
        self._print("2. SOLO INTRO")
        self._print("3. SOLO OUTRO")
        self._print("4. INTRO + OUTRO")
        mode = self._select_from_list(modes)
        if mode == "none":
            return None

        assets = self.intro_outro_catalog.discover()
        if not assets:
            raise FileNotFoundError(
                "No hay archivos MP4 disponibles en "
                "assets/videos/intro_outro/."
            )

        intro = None
        outro = None
        if mode in {"intro", "both"}:
            intro = IntroOutroSelection(
                self._select_studio_intro_outro_asset(assets, "INTRO"),
                "intro",
            )
        if mode in {"outro", "both"}:
            outro = IntroOutroSelection(
                self._select_studio_intro_outro_asset(assets, "OUTRO"),
                "outro",
            )
        return IntroOutroPlan(intro=intro, outro=outro)

    def _select_studio_intro_outro_asset(self, assets, position):
        self._print(f"\nSELECCIONAR {position}\n")
        for index, asset_path in enumerate(assets, start=1):
            self._print(f"{index}. {asset_path.name}")
        return self._select_from_list(assets)

    def select_voice_config(self):
        configs_path = Path(
            "config/voice_configs"
        )

        configs = sorted(
            configs_path.glob("*.json")
        )

        if not configs:
            raise FileNotFoundError(
                "No se encontraron configuraciones en "
                "config/voice_configs."
            )

        self._print(
            "\nVOZ\n"
        )

        for i, config in enumerate(
            configs,
            start=1
        ):
            self._print(
                f"{i}. "
                f"{self._voice_label(config.stem)}"
            )

        selected = self._select_from_list(
            configs
        )

        return selected.stem

    def select_music_category(self):
        options = [
            None,
            "random"
        ]

        self._print("\nMÚSICA\n")
        self._print("1. Sin música")
        self._print("2. Aleatoria")

        selected = self._select_from_list(
            options
        )

        return selected

    def select_overlays_mode(self):
        options = [
            "smart",
            "off"
        ]

        self._print("\nOVERLAYS\n")
        self._print("1. Sí")
        self._print("2. No")

        selected = self._select_from_list(
            options
        )

        return selected

    def select_intro_outro(self):
        self._print("\nINTRO / OUTRO\n")
        self._print("\u00bfUTILIZAR INTRO / OUTRO?")
        self._print("1. No")
        self._print("2. S\u00ed")

        enabled = self._select_from_list(
            (False, True)
        )
        if not enabled:
            return None

        assets = self.intro_outro_catalog.discover()
        if not assets:
            self._print(
                "\nNo hay archivos MP4 disponibles en "
                "assets/videos/intro_outro/."
            )
            return None

        self._print("\nSELECCIONAR ARCHIVO\n")
        for index, asset_path in enumerate(
            assets,
            start=1,
        ):
            self._print(
                f"{index}. {asset_path.name}"
            )
        asset_path = self._select_from_list(
            assets
        )

        positions = ("intro", "outro")
        self._print("\nPOSICI\u00d3N\n")
        self._print("1. INTRO")
        self._print("2. OUTRO")
        position = self._select_from_list(
            positions
        )

        return IntroOutroSelection(
            asset_path=asset_path,
            position=position,
        )

    def ask_project_name(self):
        self._print(
            "\nPROYECTO\n"
        )

        while True:
            name = input(
                "Nombre: "
            ).strip()

            if name == "0":
                self._exit_application()

            if name:
                return name

            self._print(
                "\nOpción no válida."
            )

    def ask_clear_output(self):
        self._print(
            "\nELIMINAR OUTPUT\n"
        )

        self._print("1. Sí")
        self._print("2. No")

        while True:
            option = input(
                "\n> "
            ).strip()

            if option == "0":
                self._exit_application()

            if option == "1":
                return True

            if option == "2":
                return False

            self._print(
                "\nOpción no válida."
            )

    def _select_from_list(
        self,
        items
    ):
        while True:
            option = input(
                "\n> "
            ).strip()

            if option == "0":
                self._exit_application()

            if option.isdigit():
                option = int(
                    option
                )

                if 1 <= option <= len(items):
                    return items[
                        option - 1
                    ]

            self._print(
                "\nOpción no válida."
            )

    def _label(
        self,
        value
    ):
        labels = {
            "youtube": "YouTube"
        }

        if value in labels:
            return labels[value]

        return (
            value.replace(
                "_",
                " "
            )
            .title()
        )

    def _voice_label(
        self,
        value
    ):
        labels = {
            "femenina": "Femenina",
            "masculina": "Masculina"
        }

        return labels.get(
            value,
            self._label(value)
        )

    def _subtitle_label(
        self,
        value
    ):
        labels = {
            "single_line": "Línea única",
            "word_by_word": "Palabra por palabra"
        }

        return labels.get(
            value,
            self._label(value)
        )

    def _profile_scope(
        self,
        script_source,
        visual_pipeline,
        design_target
    ):
        if script_source == "manual":
            return "script"

        if script_source == "manual_design":
            return f"design_{design_target}"

        return visual_pipeline

    def _run_studio(self):
        profile = self.select_profile("studio")
        profile_key = profile["profile_key"]
        subtitle_config = self.select_studio_subtitle_config(
            profile_key
        )
        light_leaks_enabled = self.select_studio_light_leaks()
        music_path = self.select_studio_music()
        intro_outro_selection = self.select_studio_intro_outro()

        return {
            "visual_pipeline": "studio",
            "script_source": "external",
            "design_target": "",
            "pipeline_mode": "studio",
            "profile_component": profile_key.component.value,
            "profile_platform": profile_key.platform.value,
            "profile_id": profile_key.profile_id,
            "subtitle_config": subtitle_config,
            "studio_light_leaks_enabled": light_leaks_enabled,
            "studio_music_path": str(music_path) if music_path else None,
            "voice_config": "",
            "music_category": None,
            "overlays_mode": "off",
            "intro_outro_selection": intro_outro_selection,
            "project_name": "",
            "clear_output": False,
        }

    def _exit_application(self):
        self._print(
            "\nFinalizando AI Visual Composer..."
        )
        sys.exit(0)

    def _print(
        self,
        message
    ):
        ProgressLogger.info(
            message
        )
