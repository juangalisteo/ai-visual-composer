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
                "name": "Image Pipeline",
                "pipeline": "image"
            },
            {
                "name": "Video Pipeline (Próximamente)",
                "pipeline": "video",
                "available": False
            }
        ]

        print("\nAI VISUAL COMPOSER\n")
        print("¿Qué pipeline deseas utilizar?\n")

        for i, pipeline in enumerate(
            pipelines,
            start=1
        ):
            print(
                f"{i}. {pipeline['name']}"
            )

        while True:
            selected = self._select_from_list(
                pipelines,
                "Selecciona un pipeline"
            )

            if selected.get(
                "available",
                True
            ):
                return selected[
                    "pipeline"
                ]

            print(
                "Video Pipeline estará disponible "
                "próximamente. Selecciona Image Pipeline "
                "para continuar."
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

        print("\nMODO DE EJECUCIÓN\n")

        for i, mode in enumerate(
            modes,
            start=1
        ):
            print(
                f"{i}. {mode['name']}"
            )

        selected = self._select_from_list(
            modes,
            "Selecciona un modo de ejecución"
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

        print("\nPERFILES DISPONIBLES\n")

        for i, item in enumerate(
            profiles,
            start=1
        ):
            print(
                f"{i}. "
                f"{item['platform']} / "
                f"{item['profile']}"
            )

        return self._select_from_list(
            profiles,
            "Selecciona un perfil"
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
            "\nCONFIGURACIONES DE SUBTÍTULOS\n"
        )

        for i, config in enumerate(
            configs,
            start=1
        ):
            print(
                f"{i}. {config.stem}"
            )

        selected = self._select_from_list(
            configs,
            "Selecciona configuración de subtítulos"
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
            "\nCONFIGURACIONES DE VOZ\n"
        )

        for i, config in enumerate(
            configs,
            start=1
        ):
            print(
                f"{i}. {config.stem}"
            )

        selected = self._select_from_list(
            configs,
            "Selecciona configuración de voz"
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

        print("\nMÚSICA DE FONDO\n")
        print("1. Sin música")

        for i, category in enumerate(
            categories,
            start=2
        ):
            print(
                f"{i}. {category}"
            )

        selected = self._select_from_list(
            options,
            "Selecciona una categoría musical"
        )

        return selected

    def ask_project_name(self):
        print(
            "\nNOMBRE DEL PROYECTO\n"
        )

        while True:
            name = input(
                "Nombre: "
            ).strip()

            if name:
                return name

            print(
                "Debes introducir un nombre."
            )

    def ask_clear_output(self):
        print(
            "\n¿Eliminar TODOS los proyectos "
            "del output?\n"
        )

        print("1. Sí")
        print("2. No")

        while True:
            option = input(
                "\nSelecciona una opción: "
            ).strip()

            if option == "1":
                return True

            if option == "2":
                return False

            print(
                "Opción no válida."
            )

    def _select_from_list(
        self,
        items,
        message
    ):
        while True:
            option = input(
                f"\n{message}: "
            ).strip()

            if option.isdigit():
                option = int(
                    option
                )

                if 1 <= option <= len(items):
                    return items[
                        option - 1
                    ]

            print(
                "Opción no válida."
            )
