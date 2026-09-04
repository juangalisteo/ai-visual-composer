import sys
from pathlib import Path

from app.shared.progress_logger import ProgressLogger
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
    ProfilePlatform,
)
from app.shared.profile_resolver import ProfileResolver


class RunController:

    def __init__(
        self,
        profile_resolver=None
    ):
        self.profile_resolver = (
            profile_resolver
            or ProfileResolver()
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
            }
            if visual_pipeline not in components:
                raise ValueError(
                    "Ámbito de perfil no soportado: "
                    f"{visual_pipeline}"
                )

            for platform in ProfilePlatform:
                profile_key = ProfileKey.for_component(
                    components[visual_pipeline],
                    platform
                )
                profile = self.profile_resolver.resolve(
                    profile_key
                )
                profiles.append({
                    "platform": platform.value,
                    "profile": "modo_conciencia",
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
                "diseno"
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
