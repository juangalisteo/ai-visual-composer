import json
from dataclasses import replace
from pathlib import Path

from app.shared.progress_logger import ProgressLogger
from app.shared.error_context import (
    ErrorContext,
    ErrorSeverity,
    ExitKind,
)
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import (
    ProfileComponent,
    ProfileKey,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_resolver import (
    SubtitleProfileResolver,
)
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.media_probe import MediaProbe
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
        media_probe=None,
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
        self.media_probe = media_probe or MediaProbe()
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
        profile_key = profile.get("profile_key")
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
                self._select_profile_subtitle_config(
                    profile_key,
                    profile.get("subtitle_profile_key"),
                )
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
                self.select_intro_outro(profile_key.platform)
            )

        project_name = self.ask_project_name()
        clear_output = self.ask_clear_output()
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
                profile_key.platform
                if profile_key
                else ""
            ),
            "profile_id": (
                profile_key.profile_id
                if profile_key
                else ""
            ),
            "profile_family": (
                profile_key.family
                if profile_key
                else "estandar"
            ),
            "subtitle_config": subtitle_config,
            "subtitle_profile_key": profile.get(
                "subtitle_profile_key"
            ),
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

        while True:
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
            "script": (ProfileComponent.GUION, True),
            "design_image": (ProfileComponent.IMAGEN, False),
            "design_video": (ProfileComponent.VIDEO, False),
            "image": (ProfileComponent.IMAGEN, True),
            "video": (ProfileComponent.VIDEO, True),
            "studio": (ProfileComponent.STUDIO, True),
        }
        if visual_pipeline in components:
            component, select_subtitles = components[visual_pipeline]
            return self._select_profile_identity(
                component,
                select_subtitles=select_subtitles,
            )
        raise ValueError(
            "Ámbito de perfil no soportado: "
            f"{visual_pipeline}"
        )

    def _select_profile_identity(self, component, select_subtitles=True):
        profiles_by_platform = {}
        for platform in self.profile_resolver.discover_platforms(component):
            descriptors = []
            for family in self.profile_resolver.discover_families(
                component,
                platform,
            ):
                descriptors.extend(
                    self.profile_resolver.discover(
                        component,
                        platform,
                        family,
                    )
                )
            if descriptors:
                profiles_by_platform[platform] = tuple(descriptors)

        self._print("\nPLATAFORMA\n")
        platforms = tuple(sorted(profiles_by_platform))
        if not platforms:
            raise FileNotFoundError(
                "No hay perfiles operacionales validos para el componente "
                "seleccionado."
            )
        for index, platform in enumerate(platforms, start=1):
            self._print(f"{index}. {self._label(platform)}")
        platform = self._select_from_list(platforms)

        operational_profiles = profiles_by_platform[platform]
        if len(operational_profiles) == 1:
            profile_key = operational_profiles[0][0]
        else:
            self._print("\nPERFIL OPERACIONAL\n")
            for index, (_, display_name) in enumerate(
                operational_profiles,
                start=1,
            ):
                self._print(f"{index}. {display_name}")
            profile_key = self._select_from_list(operational_profiles)[0]

        selection = {
            "path": self.profile_resolver.resolve(profile_key),
            "profile_key": profile_key,
        }
        if not select_subtitles:
            return selection

        families = self.subtitle_profile_resolver.discover_families(component, platform)
        if not families:
            raise FileNotFoundError(
                "No hay familias de subtitulos para la plataforma "
                f"{platform}."
            )
        self._print("\nSUBTÍTULOS\n")
        self._print("FAMILIA\n")
        for index, family in enumerate(families, start=1):
            self._print(f"{index}. {self._family_label(family)}")
        family = self._select_from_list(families)
        profiles = self.subtitle_profile_resolver.discover_profiles_for_family(
            component, platform, family,
        )
        self._print("\nPERFIL\n")
        for index, descriptor in enumerate(profiles, start=1):
            self._print(f"{index}. {descriptor.display_name}")
        subtitle_key = self._select_from_list(profiles).key
        selection["subtitle_profile_key"] = subtitle_key
        return selection

    def _available_profile_families(self, component, platform):
        """Return valid operational profile families for one component/platform."""
        return self.profile_resolver.discover_families(component, platform)

    @staticmethod
    def _family_label(family):
        return family.replace("_", " ").upper()

    def select_subtitle_config(self, profile_key=None):
        if profile_key is not None:
            return self._select_subtitle_profile(
                profile_key,
                "\nSUBTÍTULOS\n",
            )

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

    def _select_profile_subtitle_config(self, profile_key, subtitle_profile_key=None):
        if subtitle_profile_key is not None:
            return subtitle_profile_key
        return self.select_subtitle_config(profile_key)

    def select_studio_subtitle_config(self, profile_key):
        return self._select_subtitle_profile(
            profile_key,
            "\nSUBTITULOS\n",
        )

    def select_studio_subtitle_options(self, profile_key, input_mode):
        if input_mode == StudioInputMode.SRT_VIDEO.value:
            return self._select_studio_srt_video_subtitle_options(profile_key)

        descriptors = self.subtitle_profile_resolver.discover_profiles(
            profile_key
        )
        selections = tuple(
            descriptor.profile_id
            for descriptor in descriptors
        )
        if input_mode == StudioInputMode.SRT_VIDEO.value:
            selections = ("original", *selections)
        self._print("\nSUBT\u00cdTULOS\n")
        for index, selection in enumerate(selections, start=1):
            label = "ORIGINAL"
            if selection != "original":
                label = next(
                    descriptor.display_name
                    for descriptor in descriptors
                    if descriptor.profile_id == selection
                )
            self._print(f"{index}. {label}")
        selection = self._select_from_list(selections)
        if selection != "original":
            return selection, False
        return "single_line", True

    def _select_studio_srt_video_subtitle_options(self, profile_key):
        descriptors = self.subtitle_profile_resolver.discover_profiles(
            profile_key
        )
        selections = tuple(descriptors)
        self._print("\nSUBTÍTULOS\n")
        for index, descriptor in enumerate(descriptors, start=1):
            self._print(f"{index}. {descriptor.display_name}")
        selection = self._select_from_list(selections)
        return selection.key, True

    def _select_subtitle_profile(self, profile_key, heading):
        descriptors = self.subtitle_profile_resolver.discover_profiles(
            profile_key
        )
        selections = tuple(
            descriptor.profile_id
            for descriptor in descriptors
        )
        self._print(heading)
        for index, descriptor in enumerate(descriptors, start=1):
            self._print(f"{index}. {descriptor.display_name}")
        return self._select_from_list(selections)

    def _studio_design_subtitle_key(self, profile_key):
        key = getattr(self, "_active_studio_design_subtitle_key", None)
        if (
            key is not None
            and key.component is profile_key.component
            and key.platform == profile_key.platform
        ):
            return key
        return None

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
        self._print("5. VIDEO + AUDIO | SRT")
        self._print("6. EXPORTAR SRT ➜  VIDEO")
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

    def select_studio_video_audio_srt_inputs(self):
        candidates = self.studio_video_audio_srt_input_service.discover(False)
        return (
            self._select_studio_input_candidate(
                "VIDEO",
                candidates.videos,
                direct=len(candidates.videos) == 1,
            ),
            self._select_studio_input_candidate(
                "AUDIO",
                candidates.audios,
                direct=len(candidates.audios) == 1,
            ),
        )

    def select_studio_video_audio_srt_subtitle(self):
        candidates = self.studio_video_audio_srt_input_service.discover(True)
        return self._select_studio_input_candidate(
            "SRT",
            candidates.subtitles,
            direct=len(candidates.subtitles) == 1,
        )

    def select_studio_video_audio_srt_plan(
        self,
        subtitles,
        video_path=None,
        audio_path=None,
        subtitle_path=None,
    ):
        if video_path is None or audio_path is None:
            video_path, audio_path = self.select_studio_video_audio_srt_inputs()
        if subtitles and subtitle_path is None:
            subtitle_path = self.select_studio_video_audio_srt_subtitle()
        return self.studio_video_audio_srt_input_service.create_plan(
            subtitles,
            video_path=video_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
        )

    def select_studio_video_audio_srt_audio_tail(self, plan):
        video_duration = self.media_probe.inspect(plan.video_path).duration
        audio_duration = self.media_probe.get_duration(plan.audio_path)
        if audio_duration >= video_duration:
            return replace(
                plan,
                video_duration=video_duration,
                audio_duration=audio_duration,
            )
        self._print("\nAUDIO MÁS CORTO QUE EL VÍDEO\n")
        self._print("1. SIN MÚSICA")
        self._print("2. CON MÚSICA")
        mode = self._select_from_list(("silence", "music"))
        music_path = (
            self.studio_music_selector.select("random")
            if mode == "music"
            else None
        )
        return replace(
            plan,
            audio_tail_mode=mode,
            music_path=music_path,
            video_duration=video_duration,
            audio_duration=audio_duration,
        )

    def select_studio_montage_plan(self, profile_key, profile):
        candidates = self.studio_montage_planning_service.discover(profile)
        self._print("\nVÍDEOS ENCONTRADOS\n")
        for clip in candidates.clips:
            self._print(f"[{clip.temporary_id}] {clip.original_name}")

        clips = self._select_studio_montage_order(candidates)
        transitions_enabled = self.select_studio_montage_transitions()
        return self.studio_montage_planning_service.create_plan(
            profile_key=profile_key,
            transitions_enabled=transitions_enabled,
            clips=clips,
        )

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

    def select_studio_intro_outro_plan(self, profile_key):
        source_paths = self.studio_intro_outro_input_service.discover_sources()
        source_path = self._select_studio_input_candidate(
            "VIDEO",
            source_paths,
            direct=len(source_paths) == 1,
        )
        modes = ("intro", "outro", "both")
        self._print("\nINTRO / OUTRO\n")
        self._print("1. SOLO INTRO")
        self._print("2. SOLO OUTRO")
        self._print("3. INTRO + OUTRO")
        mode = self._select_from_list(modes)

        intro = None
        outro = None
        if mode in {"intro", "both"}:
            assets = self._require_intro_outro_assets(
                profile_key.platform,
                "intro",
            )
            intro = IntroOutroSelection(
                self._select_intro_outro_asset(assets, "INTRO"),
                "intro",
            )
        if mode in {"outro", "both"}:
            assets = self._require_intro_outro_assets(
                profile_key.platform,
                "outro",
            )
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

    def select_studio_intro_outro(self, profile_key):
        return self.select_intro_outro(profile_key.platform)

    def select_intro_outro(self, platform):
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
            assets = self._require_intro_outro_assets(platform, "intro")
            intro = IntroOutroSelection(
                self._select_intro_outro_asset(assets, "INTRO"),
                "intro",
            )
        if mode in {"outro", "both"}:
            assets = self._require_intro_outro_assets(platform, "outro")
            outro = IntroOutroSelection(
                self._select_intro_outro_asset(assets, "OUTRO"),
                "outro",
            )
        return IntroOutroPlan(intro=intro, outro=outro)

    def _require_intro_outro_assets(self, platform, position):
        assets = self.intro_outro_catalog.discover(platform, position)
        if not assets:
            raise FileNotFoundError(
                "No hay archivos MP4 disponibles para "
                f"{position.upper()} en assets/videos/intro_outro/"
                f"{platform}/{position}/."
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
            "random",
            None,
        ]

        self._print("\nMÚSICA\n")
        self._print("1. Aleatoria")
        self._print("2. Sin música")

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
            profile_key, _ = self._select_studio_operational_profile()
            video_path, audio_path = self.select_studio_video_audio_srt_inputs()
            self._print("\nSUBTÍTULOS\n")
            self._print("1. Sí")
            self._print("2. No")
            enabled = self._select_from_list((True, False))
            subtitle_config = None
            subtitle_profile_key = None
            subtitle_path = None
            if enabled:
                subtitle_path = self.select_studio_video_audio_srt_subtitle()
                subtitle_profile_key = (
                    self._select_studio_video_audio_srt_subtitle_profile(
                        profile_key
                    )
                )
                subtitle_config = subtitle_profile_key.profile_id
            plan = self.select_studio_video_audio_srt_plan(
                enabled,
                video_path=video_path,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
            )
            plan = self.select_studio_video_audio_srt_audio_tail(plan)
            return {
                "visual_pipeline": "studio",
                "script_source": "external",
                "design_target": "",
                "pipeline_mode": "studio",
                "subtitle_config": subtitle_config,
                "studio_input_mode": input_mode,
                "studio_video_audio_srt_plan": plan,
                "voice_config": "",
                "music_category": None,
                "project_name": self.ask_project_name(),
                "clear_output": self.ask_clear_output(),
                **self._studio_operational_profile_options(profile_key),
                **(
                    {"subtitle_profile_key": subtitle_profile_key}
                    if subtitle_profile_key is not None
                    else {}
                ),
            }
        if input_mode == StudioInputMode.INTRO_OUTRO.value:
            profile_key, _ = self._select_studio_operational_profile()
            intro_outro_plan = self.select_studio_intro_outro_plan(profile_key)
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
                **self._studio_operational_profile_options(profile_key),
            }
        if input_mode == StudioInputMode.MONTAJE_VIDEOS.value:
            profile_key, studio_profile = self._select_studio_operational_profile()
            montage_plan = self.select_studio_montage_plan(
                profile_key,
                studio_profile,
            )
            music_path = self.select_studio_music()
            intro_outro_selection = self.select_studio_intro_outro(profile_key)
            project_name = self.ask_project_name()
            clear_output = self.ask_clear_output()
            return {
                "visual_pipeline": "studio",
                "script_source": "external",
                "design_target": "",
                "pipeline_mode": "studio",
                "subtitle_config": None,
                "studio_input_mode": input_mode,
                "studio_montage_plan": montage_plan,
                "studio_music_path": str(music_path) if music_path else None,
                "voice_config": "",
                "music_category": None,
                "intro_outro_selection": intro_outro_selection,
                "project_name": project_name,
                "clear_output": clear_output,
                **self._studio_operational_profile_options(profile_key),
            }
        if input_mode == StudioInputMode.EXPORTAR_SRT.value:
            export_mode = self.select_studio_subtitle_export_mode()
            export_plan = self.select_studio_subtitle_export_plan(export_mode)
            subtitle_config = None
            profile_key = None
            if export_mode is StudioSubtitleExportMode.CONVERTIR:
                profile_key, _ = self._select_studio_profile()
                subtitle_config = self._active_studio_subtitle_key.profile_id
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
        profile_key, studio_profile = self._select_studio_profile(input_mode)
        prepared_input = self.select_studio_input_files(
            studio_profile,
            input_mode,
        )
        subtitle_config = self._active_studio_subtitle_key.profile_id
        subtitle_original = self._active_studio_subtitle_original
        music_path = self.select_studio_music()
        intro_outro_selection = self.select_studio_intro_outro(profile_key)
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

    def _select_studio_profile(self, input_mode=None):
        profiles_by_platform = self._studio_operational_profiles_by_platform()
        platform = self._select_studio_operational_platform(
            profiles_by_platform,
        )
        profile_key, studio_profile = self._select_studio_operational_profile(
            platform=platform,
            profiles_by_platform=profiles_by_platform,
        )
        subtitle_key, subtitle_original = self._select_studio_subtitle_profile(
            input_mode,
            platform=platform,
        )
        self._active_studio_subtitle_key = subtitle_key
        self._active_studio_subtitle_original = subtitle_original
        return profile_key, studio_profile

    def _studio_operational_profiles_by_platform(self):
        component = ProfileComponent.STUDIO
        profiles_by_platform = {}
        for platform in self.profile_resolver.discover_platforms(component):
            descriptors = []
            for family in self.profile_resolver.discover_families(
                component,
                platform,
            ):
                descriptors.extend(
                    self.profile_resolver.discover(component, platform, family)
                )
            if descriptors:
                profiles_by_platform[platform] = tuple(descriptors)
        return profiles_by_platform

    def _select_studio_operational_platform(self, profiles_by_platform):
        platforms = tuple(sorted(profiles_by_platform))
        if not platforms:
            raise FileNotFoundError(
                "No hay perfiles operacionales STUDIO disponibles."
            )
        self._print("\nPLATAFORMA\n")
        for index, platform in enumerate(platforms, start=1):
            self._print(f"{index}. {self._label(platform)}")
        return self._select_from_list(platforms)

    def _select_studio_operational_profile(
        self,
        platform=None,
        profiles_by_platform=None,
    ):
        profiles_by_platform = (
            profiles_by_platform
            if profiles_by_platform is not None
            else self._studio_operational_profiles_by_platform()
        )
        if platform is None:
            platform = self._select_studio_operational_platform(
                profiles_by_platform,
            )

        if platform not in profiles_by_platform:
            raise FileNotFoundError(
                "No hay perfiles operacionales STUDIO para la plataforma "
                f"{platform}."
            )
        descriptors = profiles_by_platform[platform]
        if len(descriptors) == 1:
            profile_key = descriptors[0][0]
        else:
            self._print("\nPERFIL OPERACIONAL\n")
            for index, (_, display_name) in enumerate(descriptors, start=1):
                self._print(f"{index}. {display_name}")
            profile_key = self._select_from_list(descriptors)[0]
        return (
            profile_key,
            self.studio_profile_loader.load(
                self.profile_resolver.load(profile_key),
                profile_key,
            ),
        )

    def _select_studio_subtitle_profile(self, input_mode, platform=None):
        component = ProfileComponent.STUDIO
        if platform is None:
            self._print("\nPLATAFORMA\n")
            platforms = self.subtitle_profile_resolver.discover_platforms(component)
            if not platforms:
                raise FileNotFoundError("No hay perfiles de subtitulos STUDIO disponibles.")
            for index, candidate in enumerate(platforms, start=1):
                self._print(f"{index}. {self._label(candidate)}")
            platform = self._select_from_list(platforms)

        self._print("\nSUBTÍTULOS\n")
        self._print("FAMILIA\n")
        families = self.subtitle_profile_resolver.discover_families(component, platform)
        for index, family in enumerate(families, start=1):
            self._print(f"{index}. {self._family_label(family)}")
        family = self._select_from_list(families)
        descriptors = self.subtitle_profile_resolver.discover_profiles_for_family(
            component, platform, family,
        )
        selections = list(descriptors)
        self._print("\nPERFIL\n")
        for index, selection in enumerate(selections, start=1):
            self._print(f"{index}. {selection.display_name}")
        selection = self._select_from_list(tuple(selections))
        return (
            selection.key,
            input_mode == StudioInputMode.SRT_VIDEO.value,
        )

    def _select_studio_video_audio_srt_subtitle_profile(self, profile_key):
        """Select a real subtitle profile within the chosen STUDIO platform."""
        component = ProfileComponent.STUDIO
        platform = profile_key.platform
        self._print("\nFAMILIA\n")
        families = self.subtitle_profile_resolver.discover_families(
            component,
            platform,
        )
        if not families:
            raise FileNotFoundError(
                "No hay familias de subtitulos STUDIO para la plataforma "
                f"{platform}."
            )
        for index, family in enumerate(families, start=1):
            self._print(f"{index}. {self._family_label(family)}")
        family = self._select_from_list(families)
        descriptors = self.subtitle_profile_resolver.discover_profiles_for_family(
            component,
            platform,
            family,
        )
        if not descriptors:
            raise FileNotFoundError(
                "No hay perfiles de subtitulos STUDIO para la familia "
                f"{family}."
            )
        self._print("\nPERFIL\n")
        for index, descriptor in enumerate(descriptors, start=1):
            self._print(f"{index}. {descriptor.display_name}")
        return self._select_from_list(descriptors).key

    def _studio_profile_options(self, profile_key):
        options = self._studio_operational_profile_options(profile_key)
        subtitle_key = getattr(self, "_active_studio_subtitle_key", None)
        if subtitle_key is not None:
            options["subtitle_profile_key"] = subtitle_key
        return options

    @staticmethod
    def _studio_operational_profile_options(profile_key):
        if profile_key is None:
            return {}
        return {
            "profile_component": profile_key.component.value,
            "profile_platform": profile_key.platform,
            "profile_id": profile_key.profile_id,
            "profile_family": profile_key.family,
        }

    def _exit_application(self):
        raise OperationalError(
            ErrorContext(
                family="CANCELLATION",
                severity=ErrorSeverity.RECOVERABLE,
                user_message="La operacion fue cancelada por el usuario.",
                exit_kind=ExitKind.CANCELLATION,
                operation="Seleccion de opciones",
            )
        )

    def _print(
        self,
        message
    ):
        ProgressLogger.info(
            message
        )
