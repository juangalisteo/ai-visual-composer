from app.controllers.interaction import labels
from app.controllers.interaction.common_options import CommonOptions
from app.controllers.interaction.contracts import (
    StudioOperationalSelection,
    StudioProfileSelection,
    StudioSubtitleSelection,
)
from app.controllers.interaction.intro_outro_selection import (
    IntroOutroSelector,
)
from app.controllers.interaction.navigation import Navigation
from app.controllers.interaction.profile_selection import ProfileSelection
from app.controllers.interaction.resource_selection import ResourceSelection
from app.controllers.interaction.subtitle_selection import SubtitleSelection
from app.controllers.interaction.studio.export_selection import (
    StudioExportSelection,
)
from app.controllers.interaction.studio.input_selection import (
    StudioInputSelection,
)
from app.controllers.interaction.studio.intro_outro_selection import (
    StudioIntroOutroRouteSelection,
)
from app.controllers.interaction.studio.montage_selection import (
    StudioMontageSelection,
)
from app.controllers.interaction.studio.video_audio_srt_selection import (
    StudioVideoAudioSrtSelection,
)
from app.controllers.interaction.terminal import Terminal
from app.shared.error_context import (
    ErrorContext,
    ErrorSeverity,
    ExitKind,
)
from app.shared.operational_error import OperationalError
from app.shared.profile_identity import (
    ProfileComponent,
)
from app.shared.profile_resolver import ProfileResolver
from app.shared.subtitle_profile_resolver import (
    SubtitleProfileResolver,
)
from app.shared.media_probe import MediaProbe
from app.modules.video.intro_outro import IntroOutroCatalog
from app.modules.audio.music_selector import MusicSelector
from app.modules.studio import (
    StudioInputMode,
    StudioInputPreparationService,
    StudioSubtitleExportInputService,
    StudioSubtitleExportMode,
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
        terminal=None,
        navigation=None,
        common_options=None,
        resource_selection=None,
        intro_outro_selection=None,
        studio_export_selection=None,
        studio_video_audio_srt_selection=None,
        studio_montage_selection=None,
        studio_intro_outro_route_selection=None,
        studio_input_selection=None,
        profile_selection=None,
        subtitle_selection=None,
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
        self.terminal = terminal or Terminal()
        self.navigation = navigation or Navigation(
            self.terminal,
            self._exit_application,
        )
        self.common_options = common_options or CommonOptions(
            self.terminal,
            self._exit_application,
        )
        self.resource_selection = resource_selection or ResourceSelection(
            self.terminal,
            self._exit_application,
            self.studio_music_selector,
        )
        self.intro_outro_selection = intro_outro_selection or IntroOutroSelector(
            self.terminal,
            self._exit_application,
            self.intro_outro_catalog,
            self.resource_selection,
        )
        self.studio_export_selection = studio_export_selection or StudioExportSelection(
            self.studio_subtitle_export_input_service,
            self.resource_selection,
        )
        self.studio_video_audio_srt_selection = (
            studio_video_audio_srt_selection or StudioVideoAudioSrtSelection(
                self.studio_video_audio_srt_input_service,
                self.resource_selection,
                self.media_probe,
                self.studio_music_selector,
            )
        )
        self.studio_montage_selection = studio_montage_selection or StudioMontageSelection(
            self.studio_montage_planning_service,
            self.terminal,
        )
        self.studio_intro_outro_route_selection = (
            studio_intro_outro_route_selection
            or StudioIntroOutroRouteSelection(
                self.studio_intro_outro_input_service,
                self.resource_selection,
            )
        )
        self.studio_input_selection = studio_input_selection or StudioInputSelection(
            self.studio_input_preparation_service,
            self.resource_selection,
        )
        self.profile_selection = profile_selection or ProfileSelection(
            self.profile_resolver,
            self.studio_profile_loader,
            self.terminal,
            self._exit_application,
        )
        self.subtitle_selection = subtitle_selection or SubtitleSelection(
            self.subtitle_profile_resolver,
            self.terminal,
            self._exit_application,
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
            subtitle_config = profile.get("subtitle_profile_key")

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
        return self.navigation.select_visual_pipeline(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_script_destination(self):
        return self.navigation.select_script_destination(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_design_target(self):
        return self.navigation.select_design_target(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_pipeline_mode(
        self,
        include_full_without_subtitles=False,
    ):
        return self.navigation.select_pipeline_mode(
            include_full_without_subtitles=include_full_without_subtitles,
            writer=self._print,
            selector=self._select_from_list,
        )

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
        selection = self.profile_selection.select_profile_identity(
            component,
            writer=self._print,
            selector=self._select_from_list,
            label=self._label,
        )
        if not select_subtitles:
            return selection
        profile_key = selection["profile_key"]
        selection["subtitle_profile_key"] = (
            self.subtitle_selection.select_profile_subtitle_profile(
                component,
                profile_key.platform,
                writer=self._print,
                selector=self._select_from_list,
                family_label=self._family_label,
                presentation_families=self._presentation_families,
            )
        )
        return selection

    @staticmethod
    def _family_label(family):
        return labels.family_label(family)

    @staticmethod
    def _presentation_families(families):
        return labels.presentation_families(families)

    def select_studio_input_mode(self):
        return self.navigation.select_studio_input_mode(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_studio_subtitle_export_mode(self):
        return self.navigation.select_studio_subtitle_export_mode(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_studio_subtitle_export_plan(self, export_mode):
        return self.studio_export_selection.select_plan(
            export_mode,
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_studio_video_audio_srt_inputs(self):
        return self.studio_video_audio_srt_selection.select_inputs(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_studio_video_audio_srt_subtitle(self):
        return self.studio_video_audio_srt_selection.select_subtitle(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_studio_video_audio_srt_plan(
        self,
        subtitles,
        video_path=None,
        audio_path=None,
        subtitle_path=None,
    ):
        return self.studio_video_audio_srt_selection.select_plan(
            subtitles,
            video_path=video_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            select_inputs=self.select_studio_video_audio_srt_inputs,
            select_subtitle=self.select_studio_video_audio_srt_subtitle,
        )

    def select_studio_video_audio_srt_audio_tail(self, plan):
        return self.studio_video_audio_srt_selection.select_audio_tail(
            plan,
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_studio_montage_plan(self, profile_key, profile):
        return self.studio_montage_selection.select_plan(
            profile_key,
            profile,
            select_order=self._select_studio_montage_order,
            select_transitions=self.select_studio_montage_transitions,
            writer=self._print,
        )

    def _select_studio_montage_order(self, candidates):
        return self.studio_montage_selection.select_order(
            candidates,
            writer=self._print,
        )

    def select_studio_montage_transitions(self):
        return self.navigation.select_studio_montage_transitions(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_studio_intro_outro_plan(self, profile_key):
        return self.studio_intro_outro_route_selection.select_plan(
            profile_key,
            require_assets=self._require_intro_outro_assets,
            select_asset=self._select_intro_outro_asset,
            writer=self._print,
            selector=self._select_from_list,
        )
    def select_studio_input_files(self, profile, input_mode):
        return self.studio_input_selection.select_files(
            profile,
            input_mode,
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_studio_music(self):
        return self.resource_selection.select_studio_music(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_studio_intro_outro(self, profile_key):
        return self.intro_outro_selection.select_studio_intro_outro(
            profile_key,
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_intro_outro(self, platform):
        return self.intro_outro_selection.select_intro_outro(
            platform,
            writer=self._print,
            selector=self._select_from_list,
        )

    def _require_intro_outro_assets(self, platform, position):
        return self.intro_outro_selection.require_assets(platform, position)

    def _select_intro_outro_asset(self, assets, position):
        return self.intro_outro_selection.select_asset(
            assets,
            position,
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_voice_config(self):
        return self.common_options.select_voice_config(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_music_category(self):
        return self.common_options.select_music_category(
            writer=self._print,
            selector=self._select_from_list,
        )

    def select_overlays_mode(self):
        return self.common_options.select_overlays_mode(
            writer=self._print,
            selector=self._select_from_list,
        )

    def ask_project_name(self):
        return self.common_options.ask_project_name(
            writer=self._print,
        )

    def ask_clear_output(self):
        return self.common_options.ask_clear_output(
            writer=self._print,
        )

    def _select_from_list(
        self,
        items
    ):
        return self.terminal.select_from_list(
            items,
            self._exit_application,
        )

    def _label(
        self,
        value
    ):
        return labels.label(value)

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
            subtitle_key = None
            if export_mode is StudioSubtitleExportMode.CONVERTIR:
                studio_selection = self._select_studio_profile_selection()
                profile_key = studio_selection.operational.operational_key
                subtitle_key = studio_selection.subtitle.subtitle_key
                subtitle_config = subtitle_key.profile_id
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
                **self._studio_profile_options(profile_key, subtitle_key),
            }
        studio_selection = self._select_studio_profile_selection(input_mode)
        profile_key = studio_selection.operational.operational_key
        studio_profile = studio_selection.operational.studio_profile
        subtitle_key = studio_selection.subtitle.subtitle_key
        prepared_input = self.select_studio_input_files(
            studio_profile,
            input_mode,
        )
        subtitle_config = subtitle_key.profile_id
        subtitle_original = studio_selection.subtitle.subtitle_original
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
            **self._studio_profile_options(profile_key, subtitle_key),
        }

    def _select_studio_profile_selection(self, input_mode=None):
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
        return StudioProfileSelection(
            operational=StudioOperationalSelection(
                operational_key=profile_key,
                studio_profile=studio_profile,
            ),
            subtitle=StudioSubtitleSelection(
                subtitle_key=subtitle_key,
                subtitle_original=subtitle_original,
            ),
        )

    def _studio_operational_profiles_by_platform(self):
        return self.profile_selection.studio_operational_profiles_by_platform()

    def _select_studio_operational_platform(self, profiles_by_platform):
        return self.profile_selection.select_studio_operational_platform(
            profiles_by_platform,
            writer=self._print,
            selector=self._select_from_list,
            label=self._label,
        )

    def _select_studio_operational_profile(
        self,
        platform=None,
        profiles_by_platform=None,
    ):
        return self.profile_selection.select_studio_operational_profile(
            platform=platform,
            profiles_by_platform=profiles_by_platform,
            profiles_by_platform_provider=(
                self._studio_operational_profiles_by_platform
            ),
            select_platform=self._select_studio_operational_platform,
            writer=self._print,
            selector=self._select_from_list,
        )

    def _select_studio_subtitle_profile(self, input_mode, platform=None):
        return self.subtitle_selection.select_studio_subtitle_profile(
            input_mode,
            platform=platform,
            writer=self._print,
            selector=self._select_from_list,
            label=self._label,
            family_label=self._family_label,
            presentation_families=self._presentation_families,
        )

    def _select_studio_video_audio_srt_subtitle_profile(self, profile_key):
        """Select a real subtitle profile within the chosen STUDIO platform."""
        return self.subtitle_selection.select_studio_video_audio_srt_subtitle_profile(
            profile_key,
            writer=self._print,
            selector=self._select_from_list,
            family_label=self._family_label,
            presentation_families=self._presentation_families,
        )

    def _studio_profile_options(self, profile_key, subtitle_key=None):
        options = self._studio_operational_profile_options(profile_key)
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
        self.terminal.write(message)
