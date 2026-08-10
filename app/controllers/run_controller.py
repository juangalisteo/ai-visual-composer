import sys
from pathlib import Path


class RunController:

    def run(self):
        visual_pipeline = self.select_visual_pipeline()
        pipeline_mode = self.select_pipeline_mode()
        profile = self.select_profile()
        subtitle_config = self.select_subtitle_config()
        voice_config = self.select_voice_config()
        music_category = self.select_music_category()
        project_name = self.ask_project_name()
        clear_output = self.ask_clear_output()

        return {
            "visual_pipeline": visual_pipeline,
            "pipeline_mode": pipeline_mode,
            "profile_path": str(profile["path"]),
            "subtitle_config": subtitle_config,
            "voice_config": voice_config,
            "music_category": music_category,
            "project_name": project_name,
            "clear_output": clear_output
        }

    def select_visual_pipeline(self):
        pipelines = [
            {
                "name": "Imagen",
                "pipeline": "image"
            },
            {
                "name": "Vídeo",
                "pipeline": "video",
                "available": False
            }
        ]

        print("\nAI VISUAL COMPOSER\n")

        for i, pipeline in enumerate(
            pipelines,
            start=1
        ):
            print(
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

            print(
                "\nNo disponible."
            )

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

        print("\nMODO\n")

        for i, mode in enumerate(
            modes,
            start=1
        ):
            print(
                f"{i}. {mode['name']}"
            )

        selected = self._select_from_list(
            modes
        )

        return selected["mode"]

    def select_profile(self):
        profiles_path = Path(
            "config/profiles"
        )

        profiles = []

        for platform in sorted(
            profiles_path.iterdir()
        ):
            if not platform.is_dir():
                continue

            for profile in sorted(
                platform.glob("*.json")
            ):
                profiles.append({
                    "platform": platform.name,
                    "profile": profile.stem,
                    "path": profile
                })

        if not profiles:
            raise FileNotFoundError(
                "No se encontraron perfiles "
                "en config/profiles."
            )

        print("\nPERFIL\n")

        for i, item in enumerate(
            profiles,
            start=1
        ):
            print(
                f"{i}. "
                f"{self._label(item['platform'])} / "
                f"{self._label(item['profile'])}"
            )

        return self._select_from_list(
            profiles
        )

    def select_subtitle_config(self):
        configs_path = Path(
            "config/subtitle_configs"
        )

        configs = sorted(
            configs_path.glob("*.json")
        )

        if not configs:
            raise FileNotFoundError(
                "No se encontraron configuraciones en "
                "config/subtitle_configs."
            )

        print(
            "\nSUBTÍTULOS\n"
        )

        for i, config in enumerate(
            configs,
            start=1
        ):
            print(
                f"{i}. "
                f"{self._subtitle_label(config.stem)}"
            )

        selected = self._select_from_list(
            configs
        )

        return selected.stem

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

        print(
            "\nVOZ\n"
        )

        for i, config in enumerate(
            configs,
            start=1
        ):
            print(
                f"{i}. "
                f"{self._voice_label(config.stem)}"
            )

        selected = self._select_from_list(
            configs
        )

        return selected.stem

    def select_music_category(self):
        music_path = Path(
            "assets/music"
        )

        if not music_path.exists():
            raise FileNotFoundError(
                "No existe la carpeta assets/music."
            )

        categories = sorted(
            folder.name
            for folder in music_path.iterdir()
            if folder.is_dir()
        )

        options = [
            None
        ] + categories

        print("\nMÚSICA\n")
        print("1. Sin música")

        for i, category in enumerate(
            categories,
            start=2
        ):
            print(
                f"{i}. {category}"
            )

        selected = self._select_from_list(
            options
        )

        return selected

    def ask_project_name(self):
        print(
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

            print(
                "\nOpción no válida."
            )

    def ask_clear_output(self):
        print(
            "\nELIMINAR OUTPUT\n"
        )

        print("1. Sí")
        print("2. No")

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

            print(
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

            print(
                "\nOpción no válida."
            )

    def _label(
        self,
        value
    ):
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

    def _exit_application(self):
        print(
            "\nFinalizando AI Visual Composer..."
        )
        sys.exit(0)