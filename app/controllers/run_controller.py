import json
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
from app.modules.studio import (
    StudioInputMode,
    StudioInputPreparationService,
    StudioSubtitleExportInputService,
    StudioSubtitleExportMode,
    StudioMontageInputError,
    StudioMontageMode,
    StudioMontagePlanningService,
    StudioProfileLoader,
    StudioIntroOutroInputService,
    StudioVideoAudioSrtInputService,
)


class RunController:

    def __init__(
        self,
        profile_resolver=None,
        subtitle_profile_resolver=None,
        intro_outro_catalog=None,
        studio_music_selector=None,
        studio_input_preparation_service=None,
        studio_subtitle_export_input_service=None,
        studio_montage_planning_service=None,
        studio_intro_outro_input_service=None,
        studio_video_audio_srt_input_service=None,
        studio_profile_loader=None,
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
        self.studio_input_preparation_service = (
            studio_input_preparation_service
            or StudioInputPreparationService()
        )
        self.studio_subtitle_export_input_service = (
            studio_subtitle_export_input_service
            or StudioSubtitleExportInputService()
        )
        self.studio_intro_outro_input_service = (
            studio_intro_outro_input_service
            or StudioIntroOutroInputService()
        )
        self.studio_video_audio_srt_input_service = studio_video_audio_srt_input_service or StudioVideoAudioSrtInputService()
        self.studio_profile_loader = (
            studio_profile_loader
            or StudioProfileLoader()
        )
        self.studio_montage_planning_service = (
            studio_montage_planning_service
            or StudioMontagePlanningService(
                self.studio_input_preparation_service
            )
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
            pipeline_mode = self.select_pipeline_mode(
                include_full_without_subtitles=(
                    script_source == "manual"
                )
            )

        produces_final_video = pipeline_mode in {
            "full",
            "full_without_subtitles",
        }

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
            profile_key = profile.get("profile_key")
            subtitle_config = (
                self._select_profile_subtitle_config(profile_key)
                if profile_key is not None
                else self.select_subtitle_config()
            )

        if pipeline_mode not in {
            "script",
            "design_image",
            "design_video"
        }:
            voice_config = self.select_voice_config()
            music_category = self.select_music_category()

        if produces_final_video:
            overlays_mode = self.select_overlays_mode()

        if produces_final_video:
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
            "profile_family": (
                profile_key.family.value
                if profile_key
                else "system"
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

    def select_pipeline_mode(
        self,
        include_full_without_subtitles=False,
    ):
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

        if include_full_without_subtitles:
            modes.append({
                "name": "Proyecto completo sin subtítulos",
                "mode": "full_without_subtitles",
            })

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
        components = {
            "script": ProfileComponent.GUION,
            "design_image": ProfileComponent.IMAGEN,
            "design_video": ProfileComponent.VIDEO,
            "image": ProfileComponent.IMAGEN,
            "video": ProfileComponent.VIDEO,
            "studio": ProfileComponent.STUDIO,
        }
        if visual_pipeline in components:
            return self._select_profile_identity(components[visual_pipeline])
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
                        else "Modo Conciencia"
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
                    f"{self._label(item['platform'])}"
                )

            self._print(
                f"{i}. {label}"
            )

        return self._select_from_list(
            profiles
        )

    def _select_profile_identity(self, component):
        self._print("\nPLATAFORMA\n")
        platforms = tuple(
            platform
            for platform in ProfilePlatform
            if self._available_profile_families(component, platform)
        )
        if not platforms:
            raise FileNotFoundError(
                "No hay perfiles validos para el componente seleccionado."
            )
        for index, platform in enumerate(platforms, start=1):
            self._print(f"{index}. {self._label(platform.value)}")
        platform = self._select_from_list(platforms)
        families = self._available_profile_families(component, platform)
        self._print("\nESTILO DE SUBTÍTULOS\n")
        labels = {"system": "ESTÁNDAR", "design": "DISEÑO"}
        for index, family in enumerate(families, start=1):
            self._print(f"{index}. {labels[family]}")
        family = self._select_from_list(families)
        if family == "system":
            system = ProfileKey.for_component(component, platform)
            return {"path": self.profile_resolver.resolve(system), "profile_key": system}
        designs = self.profile_resolver.discover(component, platform, "design")
        self._print("\nDISEÑO\n")
        for index, (_, display_name) in enumerate(designs, start=1):
            self._print(f"{index}. {display_name}")
        profile_key, _ = self._select_from_list(designs)
        return {"path": self.profile_resolver.resolve(profile_key), "profile_key": profile_key}

    def _available_profile_families(self, component, platform):
        """Return families only when their on-disk subtitle profiles validate."""
        families = []
        system = ProfileKey.for_component(component, platform)
        try:
            self.profile_resolver.load(system)
            self.subtitle_profile_resolver.discover_styles(system)
        except (FileNotFoundError, TypeError, ValueError, json.JSONDecodeError):
            pass
        else:
            families.append("system")

        designs = self.profile_resolver.discover(component, platform, "design")
        for design, _ in designs:
            try:
                self.subtitle_profile_resolver.discover_styles(design)
            except (FileNotFoundError, TypeError, ValueError, json.JSONDecodeError):
                continue
            families.append("design")
            break
        return tuple(families)

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

    def _select_profile_subtitle_config(self, profile_key):
        automatic_style = self._automatic_subtitle_style(profile_key)
        if automatic_style is not None:
            return automatic_style
        return self.select_subtitle_config()

    def _automatic_subtitle_style(self, profile_key):
        style = self.profile_resolver.declared_subtitle_style(profile_key)
        if style is None:
            return None
        style = style.value if hasattr(style, "value") else style
        available = self.subtitle_profile_resolver.discover_styles(profile_key)
        if style not in available:
            raise ValueError(
                "El estilo declarado por el perfil DESIGN no tiene "
                "un SubtitleProfile válido: "
                f"{profile_key.profile_id} / {style}"
            )
        return style

    def select_studio_subtitle_config(self, profile_key):
        automatic_style = self._automatic_subtitle_style(profile_key)
        if automatic_style is not None:
            return automatic_style
        configs = self.subtitle_profile_resolver.discover_styles(
            profile_key
        )

        self._print("\nSUBTITULOS\n")
        for index, config in enumerate(configs, start=1):
            self._print(
                f"{index}. {self._subtitle_label(config)}"
            )

        return self._select_from_list(configs)

    def select_studio_subtitle_options(self, profile_key, input_mode):
        automatic_style = self._automatic_subtitle_style(profile_key)
        if automatic_style is not None:
            return automatic_style, False
        modes = ("single_line", "word_by_word")
        if input_mode in {
            StudioInputMode.SRT_VIDEO.value,
            StudioInputMode.VIDEO_AUDIO_SRT.value,
        }:
            modes = ("original", *modes)
        labels = {
            "original": "ORIGINAL",
            "single_line": "L\u00cdNEA \u00daNICA",
            "word_by_word": "PALABRA POR PALABRA",
        }
        self._print("\nSUBT\u00cdTULOS\n")
        for index, mode in enumerate(modes, start=1):
            self._print(f"{index}. {labels[mode]}")
        mode = self._select_from_list(modes)
        if mode != "original":
            return mode, False
        return "single_line", True

    def select_studio_montage_subtitle_options(self, profile_key):
        self._print("\nSUBTÍTULOS\n")
        self._print("1. Sí")
        self._print("2. No")
        subtitles_enabled = self._select_from_list((True, False))
        if not subtitles_enabled:
            return False, ""

        automatic_style = self._automatic_subtitle_style(profile_key)
        if automatic_style is not None:
            return True, automatic_style

        configs = self.subtitle_profile_resolver.discover_styles(
            profile_key
        )
        self._print("\nESTILO DE SUBTÍTULOS\n")
        for index, config in enumerate(configs, start=1):
            self._print(
                f"{index}. {self._subtitle_label(config)}"
            )
        return True, self._select_from_list(configs)

    def select_studio_input_mode(self):
        modes = (
            StudioInputMode.VIDEO.value,
            StudioInputMode.SRT_VIDEO.value,
            StudioInputMode.INTRO_OUTRO.value,
            StudioInputMode.MONTAJE_VIDEOS.value,
            StudioInputMode.VIDEO_AUDIO_SRT.value,
            StudioInputMode.EXPORTAR_SRT.value,
        )
        self._print("\nENTRADA\n")
        self._print("1. SOLO VIDEO")
        self._print("2. SRT + VIDEO")
        self._print("3. INTRO / OUTRO")
        self._print("4. MONTAJE VÍDEOS")
        self._print("5. VIDEO + AUDIO SRT")
        self._print("6. EXPORTAR SRT VIDEO")
        return self._select_from_list(modes)

    def select_studio_subtitle_export_mode(self):
        modes = (
            StudioSubtitleExportMode.TRANSCRIBIR,
            StudioSubtitleExportMode.CONVERTIR,
        )
        self._print("\nMODO\n")
        self._print("1. TRANSCRIBIR")
        self._print("2. CONVERTIR")
        return self._select_from_list(modes)

    def select_studio_subtitle_export_plan(self, export_mode):
        candidates = self.studio_subtitle_export_input_service.discover(
            export_mode
        )
        label = (
            "MEDIA"
            if candidates.mode is StudioSubtitleExportMode.TRANSCRIBIR
            else "SRT"
        )
        source_path = self._select_studio_input_candidate(
            label,
            candidates.sources,
            direct=len(candidates.sources) == 1,
        )
        return self.studio_subtitle_export_input_service.prepare(
            candidates.mode,
            source_path=source_path,
        )

    def select_studio_video_audio_srt_plan(self, subtitles):
        candidates = self.studio_video_audio_srt_input_service.discover(
            subtitles,
        )
        video_path = self._select_studio_input_candidate(
            "VIDEO",
            candidates.videos,
            direct=len(candidates.videos) == 1,
        )
        audio_path = self._select_studio_input_candidate(
            "AUDIO",
            candidates.audios,
            direct=len(candidates.audios) == 1,
        )
        subtitle_path = None
        if subtitles:
            subtitle_path = self._select_studio_input_candidate(
                "SRT",
                candidates.subtitles,
                direct=len(candidates.subtitles) == 1,
            )
        return self.studio_video_audio_srt_input_service.create_plan(
            subtitles,
            video_path=video_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
        )

    def select_studio_montage_plan(self, profile_key, profile):
        mode = self.select_studio_montage_mode()
        candidates = self.studio_montage_planning_service.discover(profile)
        self._print("\nVÍDEOS ENCONTRADOS\n")
        for clip in candidates.clips:
            self._print(f"[{clip.temporary_id}] {clip.original_name}")

        clips = self._select_studio_montage_order(candidates)
        transitions_enabled = self.select_studio_montage_transitions()
        return self.studio_montage_planning_service.create_plan(
            profile_key=profile_key,
            mode=mode,
            transitions_enabled=transitions_enabled,
            clips=clips,
        )

    def select_studio_montage_mode(self):
        modes = (
            StudioMontageMode.SOLO_MONTAJE,
            StudioMontageMode.MONTAJE_COMPLETO,
        )
        self._print("\nMODO\n")
        self._print("1. SOLO MONTAJE")
        self._print("2. MONTAJE COMPLETO")
        return self._select_from_list(modes)

    def _select_studio_montage_order(self, candidates):
        self._print("\nIntroduce el orden de montaje:")
        while True:
            try:
                return self.studio_montage_planning_service.parse_order(
                    input("\n> "),
                    candidates,
                )
            except StudioMontageInputError as error:
                self._print(f"\n{error}")

    def select_studio_montage_transitions(self):
        self._print("\nTRANSICIONES\n")
        self._print("1. Sí")
        self._print("2. No")
        return self._select_from_list((True, False))

    def select_studio_intro_outro_plan(self):
        source_path = self.studio_intro_outro_input_service.discover_source()
        modes = ("intro", "outro", "both")
        self._print("\nINTRO / OUTRO\n")
        self._print("1. SOLO INTRO")
        self._print("2. SOLO OUTRO")
        self._print("3. INTRO + OUTRO")
        mode = self._select_from_list(modes)

        intro = None
        outro = None
        if mode in {"intro", "both"}:
            assets = self._require_intro_outro_assets("intro")
            intro = IntroOutroSelection(
                self._select_intro_outro_asset(assets, "INTRO"),
                "intro",
            )
        if mode in {"outro", "both"}:
            assets = self._require_intro_outro_assets("outro")
            outro = IntroOutroSelection(
                self._select_intro_outro_asset(assets, "OUTRO"),
                "outro",
            )
        return self.studio_intro_outro_input_service.create_plan(
            IntroOutroPlan(intro=intro, outro=outro),
            source_path=source_path,
        )
    def select_studio_input_files(self, profile, input_mode):
        candidates = self.studio_input_preparation_service.discover(
            profile,
            input_mode,
        )
        if candidates.mode is StudioInputMode.VIDEO:
            video_path = self._select_studio_input_candidate(
                "VIDEO",
                candidates.videos,
                direct=len(candidates.videos) == 1,
            )
            return self.studio_input_preparation_service.prepare(
                profile,
                candidates.mode,
                video_path=video_path,
            )

        direct = (
            len(candidates.videos) == 1
            and len(candidates.subtitles) == 1
        )
        video_path = self._select_studio_input_candidate(
            "VIDEO",
            candidates.videos,
            direct=direct,
        )
        subtitle_path = self._select_studio_input_candidate(
            "SRT",
            candidates.subtitles,
            direct=direct,
        )
        return self.studio_input_preparation_service.prepare(
            profile,
            candidates.mode,
            video_path=video_path,
            subtitle_path=subtitle_path,
        )

    def _select_studio_input_candidate(self, label, candidates, direct):
        if direct:
            return candidates[0]

        self._print(f"\n{label}\n")
        for index, candidate in enumerate(candidates, start=1):
            self._print(f"{index}. {candidate.name}")
        return self._select_from_list(candidates)

    def select_studio_music(self):
        self._print("\nMÚSICA\n")
        self._print("1. Sí")
        self._print("2. No")
        enabled = self._select_from_list((True, False))
        if not enabled:
            return None

        return self.studio_music_selector.select("random")

    def select_studio_intro_outro(self):
        return self.select_intro_outro()

    def select_intro_outro(self):
        modes = ("none", "intro", "outro", "both")
        self._print("\nINTRO / OUTRO\n")
        self._print("1. NINGUNO")
        self._print("2. SOLO INTRO")
        self._print("3. SOLO OUTRO")
        self._print("4. INTRO + OUTRO")
        mode = self._select_from_list(modes)
        if mode == "none":
            return None

        intro = None
        outro = None
        if mode in {"intro", "both"}:
            assets = self._require_intro_outro_assets("intro")
            intro = IntroOutroSelection(
                self._select_intro_outro_asset(assets, "INTRO"),
                "intro",
            )
        if mode in {"outro", "both"}:
            assets = self._require_intro_outro_assets("outro")
            outro = IntroOutroSelection(
                self._select_intro_outro_asset(assets, "OUTRO"),
                "outro",
            )
        return IntroOutroPlan(intro=intro, outro=outro)

    def _require_intro_outro_assets(self, position):
        assets = self.intro_outro_catalog.discover(position)
        if not assets:
            raise FileNotFoundError(
                "No hay archivos MP4 disponibles para "
                f"{position.upper()} en assets/videos/intro_outro/{position}/."
            )
        return assets

    def _select_intro_outro_asset(self, assets, position):
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
            "on",
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

    def _run_studio(self):
        input_mode = self.select_studio_input_mode()
        if input_mode == StudioInputMode.VIDEO_AUDIO_SRT.value:
            profile_key, _ = self._select_studio_profile()
            self._print("\nSUBTÍTULOS\n")
            self._print("1. NO")
            self._print("2. SÍ")
            enabled = self._select_from_list((False, True))
            plan = self.select_studio_video_audio_srt_plan(enabled)
            subtitle_config = None
            subtitle_original = False
            if enabled:
                subtitle_config, subtitle_original = (
                    self.select_studio_subtitle_options(
                        profile_key,
                        input_mode,
                    )
                )
            return {
                "visual_pipeline": "studio",
                "script_source": "external",
                "design_target": "",
                "pipeline_mode": "studio",
                "subtitle_config": subtitle_config,
                "studio_input_mode": input_mode,
                "studio_video_audio_srt_plan": plan,
                "studio_subtitle_original": subtitle_original,
                "voice_config": "",
                "music_category": None,
                "project_name": self.ask_project_name(),
                "clear_output": self.ask_clear_output(),
                **self._studio_profile_options(profile_key),
            }
        if input_mode == StudioInputMode.INTRO_OUTRO.value:
            profile_key, _ = self._select_studio_profile()
            intro_outro_plan = self.select_studio_intro_outro_plan()
            project_name = self.ask_project_name()
            clear_output = self.ask_clear_output()
            return {
                "visual_pipeline": "studio",
                "script_source": "external",
                "design_target": "",
                "pipeline_mode": "studio",
                "subtitle_config": None,
                "studio_input_mode": input_mode,
                "studio_intro_outro_plan": intro_outro_plan,
                "voice_config": "",
                "music_category": None,
                "project_name": project_name,
                "clear_output": clear_output,
                **self._studio_profile_options(profile_key),
            }
        if input_mode == StudioInputMode.MONTAJE_VIDEOS.value:
            profile_key, studio_profile = self._select_studio_profile()
            montage_plan = self.select_studio_montage_plan(
                profile_key,
                studio_profile,
            )
            subtitle_config = ""
            subtitles_enabled = None
            music_path = None
            intro_outro_selection = None
            if montage_plan.mode is StudioMontageMode.MONTAJE_COMPLETO:
                subtitles_enabled, subtitle_config = (
                    self.select_studio_montage_subtitle_options(
                        profile_key
                    )
                )
                music_path = self.select_studio_music()
                intro_outro_selection = self.select_studio_intro_outro()
            project_name = self.ask_project_name()
            clear_output = self.ask_clear_output()
            return {
                "visual_pipeline": "studio",
                "script_source": "external",
                "design_target": "",
                "pipeline_mode": "studio",
                "subtitle_config": subtitle_config,
                "studio_subtitles_enabled": subtitles_enabled,
                "studio_input_mode": input_mode,
                "studio_montage_plan": montage_plan,
                "studio_music_path": str(music_path) if music_path else None,
                "voice_config": "",
                "music_category": None,
                "intro_outro_selection": intro_outro_selection,
                "project_name": project_name,
                "clear_output": clear_output,
                **self._studio_profile_options(profile_key),
            }
        if input_mode == StudioInputMode.EXPORTAR_SRT.value:
            export_mode = self.select_studio_subtitle_export_mode()
            export_plan = self.select_studio_subtitle_export_plan(export_mode)
            subtitle_config = None
            profile_key = None
            if export_mode is StudioSubtitleExportMode.CONVERTIR:
                profile_key, _ = self._select_studio_profile()
                subtitle_config = self.select_studio_subtitle_config(
                    profile_key
                )
            project_name = self.ask_project_name()
            clear_output = self.ask_clear_output()
            return {
                "visual_pipeline": "studio",
                "script_source": "external",
                "design_target": "",
                "pipeline_mode": "studio",
                "subtitle_config": subtitle_config,
                "studio_input_mode": input_mode,
                "studio_subtitle_export_plan": export_plan,
                "voice_config": "",
                "music_category": None,
                "project_name": project_name,
                "clear_output": clear_output,
                **self._studio_profile_options(profile_key),
            }
        profile_key, studio_profile = self._select_studio_profile()
        prepared_input = self.select_studio_input_files(
            studio_profile,
            input_mode,
        )
        subtitle_config, subtitle_original = self.select_studio_subtitle_options(
            profile_key,
            input_mode,
        )
        music_path = self.select_studio_music()
        intro_outro_selection = self.select_studio_intro_outro()
        project_name = self.ask_project_name()
        clear_output = self.ask_clear_output()

        return {
            "visual_pipeline": "studio",
            "script_source": "external",
            "design_target": "",
            "pipeline_mode": "studio",
            "subtitle_config": subtitle_config,
            "studio_subtitle_original": subtitle_original,
            "studio_input_mode": input_mode,
            "studio_video_path": str(prepared_input.video_path),
            "studio_subtitle_path": (
                str(prepared_input.subtitle_path)
                if prepared_input.subtitle_path is not None
                else None
            ),
            "studio_music_path": str(music_path) if music_path else None,
            "voice_config": "",
            "music_category": None,
            "intro_outro_selection": intro_outro_selection,
            "project_name": project_name,
            "clear_output": clear_output,
            **self._studio_profile_options(profile_key),
        }

    def _select_studio_profile(self):
        profile = self.select_profile("studio")
        profile_key = profile["profile_key"]
        return (
            profile_key,
            self.studio_profile_loader.load(
                self.profile_resolver.load(profile_key),
                profile_key,
            ),
        )

    @staticmethod
    def _studio_profile_options(profile_key):
        if profile_key is None:
            return {}
        return {
            "profile_component": profile_key.component.value,
            "profile_platform": profile_key.platform.value,
            "profile_id": profile_key.profile_id,
            "profile_family": profile_key.family.value,
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
