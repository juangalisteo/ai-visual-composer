"""Coordination for the standard STUDIO execution route."""

import shutil
import time
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from app.managers.project_manager import ProjectManager
from app.modules.studio.intro_outro import StudioIntroOutroPlan
from app.modules.studio.input_preparation import (
    StudioInputMode,
    StudioInputPreparationService,
)
from app.modules.studio.montage import (
    StudioMontagePlan,
    StudioMontageRenderResult,
    StudioMontageService,
)
from app.modules.studio.profile import (
    StudioPreparation,
    StudioProfileLoader,
)
from app.modules.studio.render_service import (
    StudioOutputPathResolver,
    StudioRenderResult,
    StudioRenderService,
)
from app.modules.studio.subtitle_export import (
    StudioSubtitleExportMode,
    StudioSubtitleExportPlan,
    StudioSubtitleExportService,
)
from app.modules.studio.video_audio_srt import (
    StudioVideoAudioSrtPlan,
    StudioVideoAudioSrtService,
)
from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.modes.registry import CueModelRegistry
from app.modules.subtitles.pipeline.cue_transformer import SubtitleCueTransformer
from app.modules.subtitles.policies.text_case import TextCasePolicy
from app.shared.config_manager import ConfigManager
from app.shared.media_probe import MediaProbe
from app.shared.profile_identity import ProfileComponent
from app.shared.profile_resolver import ProfileResolver
from app.shared.progress_logger import ProgressLogger


class StudioExecutionCoordinator:
    """Coordinate the typed STUDIO preparation and execution routes."""

    def prepare_standard(
        self,
        input_mode=None,
        subtitle_profile_key=None,
        config_manager=None,
        profile_loader=None,
        input_preparation_service=None,
        media_probe=None,
        video_path=None,
        subtitle_path=None,
        subtitle_original=False,
        subtitle_profile_key_normalizer=None,
    ):
        """Validate and transport standard STUDIO inputs without a project."""
        config = config_manager or ConfigManager()
        profile_key = config.get_operational_profile_key()
        if profile_key is None:
            raise ValueError(
                "STUDIO requiere una identidad de perfil estructurada."
            )
        if profile_key.component is not ProfileComponent.STUDIO:
            raise ValueError(
                "La ejecucion STUDIO requiere component=studio."
            )

        profile = (profile_loader or StudioProfileLoader()).load(
            config.get_profile_config(),
            profile_key,
        )
        if subtitle_profile_key_normalizer is None:
            raise TypeError(
                "STUDIO requiere un normalizador de SubtitleProfileKey."
            )
        subtitle_profile_key = subtitle_profile_key_normalizer(
            subtitle_profile_key=subtitle_profile_key,
        )
        subtitle_profile = config.get_subtitle_profile_by_key(
            subtitle_profile_key,
        )
        preparation_options = {}
        if video_path is not None:
            preparation_options["video_path"] = video_path
        if subtitle_path is not None:
            preparation_options["subtitle_path"] = subtitle_path
        prepared_input = (
            input_preparation_service
            or StudioInputPreparationService()
        ).prepare(
            profile,
            input_mode,
            **preparation_options,
        )

        if prepared_input.mode is StudioInputMode.VIDEO:
            media_info = (
                media_probe
                or MediaProbe()
            ).inspect(prepared_input.video_path)
            if not media_info.has_audio:
                raise ValueError(
                    "El video seleccionado no contiene una pista de audio. "
                    "SOLO VIDEO necesita audio para generar los subtitulos."
                )

        return StudioPreparation(
            profile_key=profile_key,
            profile=profile,
            subtitle_profile=subtitle_profile,
            video_path=prepared_input.video_path,
            subtitle_path=prepared_input.subtitle_path,
            input_mode=prepared_input.mode.value,
            subtitle_original=bool(subtitle_original),
        )

    @staticmethod
    def prepare_montage(montage_plan):
        """Validate the structured STUDIO montage boundary."""
        if not isinstance(montage_plan, StudioMontagePlan):
            raise TypeError(
                "MONTAJE DE VÍDEOS requiere un plan STUDIO estructurado."
            )
        return montage_plan

    def run_standard(
        self,
        input_mode=None,
        subtitle_profile_key=None,
        music_path=None,
        intro_outro_selection=None,
        preparation_service=None,
        render_service=None,
        output_path_resolver=None,
        external_subtitle_preparation_service=None,
        project=None,
        video_path=None,
        subtitle_path=None,
        subtitle_original=False,
        config_manager=None,
        subtitle_profile_key_normalizer=None,
        persist_subtitle_base=None,
        persist_render_subtitle=None,
        with_subtitle_artifacts=None,
    ):
        """Run the standard STUDIO route with existing collaborators."""
        if (
            subtitle_original
            and input_mode != StudioInputMode.SRT_VIDEO.value
        ):
            raise ValueError(
                "ORIGINAL solo esta disponible para STUDIO SRT + VIDEO."
            )
        preparation_options = {"input_mode": input_mode}
        if subtitle_profile_key is not None:
            preparation_options["subtitle_profile_key"] = (
                subtitle_profile_key
            )
        if subtitle_original:
            preparation_options["subtitle_original"] = True
        if video_path is not None:
            preparation_options["video_path"] = video_path
        if subtitle_path is not None:
            preparation_options["subtitle_path"] = subtitle_path
        if preparation_service is None:
            preparation = self.prepare_standard(
                **preparation_options,
                config_manager=config_manager,
                subtitle_profile_key_normalizer=(
                    subtitle_profile_key_normalizer
                ),
            )
        else:
            preparation = preparation_service(**preparation_options)
        if project is None:
            project = ProjectManager()
            project.setup()
        output_path = (
            output_path_resolver
            or StudioOutputPathResolver()
        ).resolve(
            profile_key=preparation.profile_key,
            project=project,
        )
        return self.render_prepared(
            preparation=preparation,
            project=project,
            music_path=music_path,
            intro_outro_selection=intro_outro_selection,
            output_path=output_path,
            render_service=render_service,
            external_subtitle_preparation_service=(
                external_subtitle_preparation_service
            ),
            persist_subtitle_base=persist_subtitle_base,
            persist_render_subtitle=persist_render_subtitle,
            with_subtitle_artifacts=with_subtitle_artifacts,
        )

    def render_prepared(
        self,
        preparation,
        project,
        music_path,
        intro_outro_selection,
        output_path,
        render_service=None,
        external_subtitle_preparation_service=None,
        persist_subtitle_base=None,
        persist_render_subtitle=None,
        with_subtitle_artifacts=None,
    ):
        """Render one prepared standard STUDIO input unchanged."""
        persist_subtitle_base = (
            persist_subtitle_base
            or self.persist_subtitle_base
        )
        persist_render_subtitle = (
            persist_render_subtitle
            or self.persist_render_subtitle
        )
        with_subtitle_artifacts = (
            with_subtitle_artifacts
            or self.with_subtitle_artifacts
        )
        subtitles_enabled = getattr(
            preparation,
            "subtitles_enabled",
            True,
        )
        render_options = {
            "video_path": preparation.video_path,
            "profile_key": preparation.profile_key,
            "music_path": music_path,
            "profile": preparation.profile,
        }
        if subtitles_enabled:
            render_options["subtitle_profile"] = preparation.subtitle_profile
        if intro_outro_selection is not None:
            render_options["intro_outro_selection"] = intro_outro_selection
        render_options["output_path"] = output_path
        renderer = render_service or StudioRenderService()
        if not subtitles_enabled:
            return renderer.render(**render_options)
        if preparation.input_mode == StudioInputMode.SRT_VIDEO.value:
            base_subtitle_path = persist_subtitle_base(
                preparation.subtitle_path,
                output_path,
            )
            render_subtitle_path = persist_render_subtitle(
                base_subtitle_path=base_subtitle_path,
                output_path=output_path,
                subtitle_profile=preparation.subtitle_profile,
                render_fps=preparation.profile.fps,
                original=getattr(preparation, "subtitle_original", False),
            )
            render_options["subtitle_path"] = render_subtitle_path
            rendered = renderer.render(**render_options)
            return with_subtitle_artifacts(
                rendered,
                base_subtitle_path=base_subtitle_path,
                render_subtitle_path=render_subtitle_path,
            )

        with TemporaryDirectory(
            prefix="ai_visual_composer_studio_whisper_"
        ) as directory:
            ProgressLogger.start(
                "PREPARANDO SUBTÍTULOS"
            )
            subtitle_preparation_start = time.perf_counter()
            subtitles = (
                external_subtitle_preparation_service
                or ExternalMediaSubtitlePreparationService()
            ).prepare(
                video_path=preparation.video_path,
                working_directory=directory,
            )
            subtitle_preparation_duration = (
                time.perf_counter()
                - subtitle_preparation_start
            )
            ProgressLogger.finish(
                "SUBTÍTULOS PREPARADOS",
                subtitle_preparation_duration,
            )
            base_subtitle_path = persist_subtitle_base(
                subtitles.subtitle_path,
                output_path,
            )
            render_subtitle_path = persist_render_subtitle(
                base_subtitle_path=base_subtitle_path,
                output_path=output_path,
                subtitle_profile=preparation.subtitle_profile,
                render_fps=preparation.profile.fps,
                timing=subtitles.timing,
                original=getattr(preparation, "subtitle_original", False),
            )
            render_options["subtitle_path"] = render_subtitle_path
            render_options["subtitle_timing"] = subtitles.timing
            rendered = renderer.render(**render_options)
            return with_subtitle_artifacts(
                rendered,
                base_subtitle_path=base_subtitle_path,
                render_subtitle_path=render_subtitle_path,
                subtitle_preparation_duration=subtitle_preparation_duration,
            )

    def run_video_audio_srt(
        self,
        plan,
        subtitle_profile_key=None,
        project=None,
        config_manager=None,
        profile_loader=None,
        output_path_resolver=None,
        service=None,
        subtitle_profile_key_normalizer=None,
        persist_subtitle_base=None,
        persist_render_subtitle=None,
    ):
        """Run the structured STUDIO VIDEO + AUDIO + SRT route."""
        if not isinstance(plan, StudioVideoAudioSrtPlan):
            raise TypeError(
                "VIDEO + AUDIO SRT requiere un plan STUDIO estructurado."
            )
        if (
            plan.subtitle_path is None
            and subtitle_profile_key is not None
        ):
            raise ValueError(
                "VIDEO + AUDIO SRT sin SRT no admite estilo de subtitulos."
            )
        if (
            plan.subtitle_path is not None
            and not subtitle_profile_key
        ):
            raise ValueError(
                "VIDEO + AUDIO SRT con SRT requiere un estilo de subtitulos."
            )

        project = project or ProjectManager()
        project.setup()
        config = config_manager or ConfigManager()
        profile_key = config.get_operational_profile_key()
        if (
            profile_key is None
            or profile_key.component is not ProfileComponent.STUDIO
        ):
            raise ValueError(
                "VIDEO + AUDIO SRT requiere identidad STUDIO estructurada."
            )
        profile = (profile_loader or StudioProfileLoader()).load(
            config.get_profile_config(),
            profile_key,
        )
        output_path = (
            output_path_resolver
            or StudioOutputPathResolver()
        ).resolve(
            profile_key=profile_key,
            project=project,
        )

        subtitle_profile = None
        base_subtitle_path = None
        render_subtitle_path = None
        render_plan = plan
        if plan.subtitle_path is not None:
            if subtitle_profile_key_normalizer is None:
                raise TypeError(
                    "STUDIO requiere un normalizador de SubtitleProfileKey."
                )
            subtitle_profile_key = subtitle_profile_key_normalizer(
                subtitle_profile_key=subtitle_profile_key,
            )
            subtitle_profile = config.get_subtitle_profile_by_key(
                subtitle_profile_key,
            )
            persist_subtitle_base = (
                persist_subtitle_base
                or self.persist_subtitle_base
            )
            persist_render_subtitle = (
                persist_render_subtitle
                or self.persist_render_subtitle
            )
            base_subtitle_path = persist_subtitle_base(
                plan.subtitle_path,
                output_path,
            )
            render_subtitle_path = persist_render_subtitle(
                base_subtitle_path=base_subtitle_path,
                output_path=output_path,
                subtitle_profile=subtitle_profile,
                render_fps=profile.fps,
                original=True,
            )
            render_plan = replace(
                plan,
                subtitle_path=render_subtitle_path,
            )

        output_path, duration, command = (
            service
            or StudioVideoAudioSrtService()
        ).render(
            render_plan,
            output_path,
            profile,
            subtitle_profile=subtitle_profile,
        )
        return type(
            "StudioVideoAudioSrtResult",
            (),
            {
                "output_path": output_path,
                "generated_duration": duration,
                "command": command,
                "base_subtitle_path": base_subtitle_path,
                "generated_subtitle_path": render_subtitle_path,
            },
        )()

    def run_subtitle_export(
        self,
        export_plan,
        subtitle_profile_key=None,
        project=None,
        config_manager=None,
        profile_loader=None,
        export_service=None,
        subtitle_profile_key_normalizer=None,
    ):
        """Run the structured STUDIO subtitle export route."""
        if not isinstance(export_plan, StudioSubtitleExportPlan):
            raise TypeError(
                "EXPORTAR SRT requiere un plan STUDIO estructurado."
            )
        project = project or ProjectManager()
        project.setup()
        service = export_service or StudioSubtitleExportService()
        if export_plan.mode is StudioSubtitleExportMode.TRANSCRIBIR:
            if subtitle_profile_key is not None:
                raise ValueError(
                    "TRANSCRIBIR no admite formato de subtitulos."
                )
            return service.export(
                plan=export_plan,
                project=project,
            )

        if subtitle_profile_key is None:
            raise ValueError("CONVERTIR requiere una SubtitleProfileKey.")
        config = config_manager or ConfigManager()
        profile_key = config.get_operational_profile_key()
        if (
            profile_key is None
            or profile_key.component is not ProfileComponent.STUDIO
        ):
            raise ValueError(
                "CONVERTIR requiere una identidad STUDIO estructurada."
            )
        profile = (profile_loader or StudioProfileLoader()).load(
            config.get_profile_config(),
            profile_key,
        )
        if subtitle_profile_key_normalizer is None:
            raise TypeError(
                "STUDIO requiere un normalizador de SubtitleProfileKey."
            )
        subtitle_profile_key = subtitle_profile_key_normalizer(
            subtitle_profile_key=subtitle_profile_key,
        )
        subtitle_profile = config.get_subtitle_profile_by_key(
            subtitle_profile_key,
        )
        return service.export(
            plan=export_plan,
            project=project,
            profile=profile,
            subtitle_profile=subtitle_profile,
        )

    def run_intro_outro(
        self,
        intro_outro_plan,
        project=None,
        config_manager=None,
        profile_loader=None,
        output_path_resolver=None,
        render_service=None,
    ):
        """Run the structured STUDIO INTRO / OUTRO route."""
        if not isinstance(intro_outro_plan, StudioIntroOutroPlan):
            raise TypeError(
                "INTRO / OUTRO requiere un plan STUDIO estructurado."
            )
        project = project or ProjectManager()
        project.setup()
        config = config_manager or ConfigManager()
        profile_key = config.get_operational_profile_key()
        if (
            profile_key is None
            or profile_key.component is not ProfileComponent.STUDIO
        ):
            raise ValueError(
                "INTRO / OUTRO requiere identidad STUDIO estructurada."
            )
        profile = (profile_loader or StudioProfileLoader()).load(
            config.get_profile_config(),
            profile_key,
        )
        output_path = (
            output_path_resolver
            or StudioOutputPathResolver()
        ).resolve(
            profile_key=profile_key,
            project=project,
        )
        return (render_service or StudioRenderService()).render(
            video_path=intro_outro_plan.source_path,
            subtitle_path=None,
            profile_key=profile_key,
            profile=profile,
            output_path=output_path,
            intro_outro_selection=intro_outro_plan.intro_outro_plan,
        )

    def run_montage(
        self,
        montage_plan,
        music_path=None,
        intro_outro_selection=None,
        project=None,
        profile_resolver=None,
        profile_loader=None,
        output_path_resolver=None,
        montage_service=None,
        render_service=None,
    ):
        """Compose and render one structured STUDIO montage."""
        montage_plan = self.prepare_montage(montage_plan)
        project = project or ProjectManager()
        project.setup()
        profile_resolver = profile_resolver or ProfileResolver()
        profile_loader = profile_loader or StudioProfileLoader()
        profile = profile_loader.load(
            profile_resolver.load_operational(montage_plan.profile_key),
            montage_plan.profile_key,
        )
        output_path = (
            output_path_resolver
            or StudioOutputPathResolver()
        ).resolve(
            profile_key=montage_plan.profile_key,
            project=project,
        )
        montage_service = montage_service or StudioMontageService()
        with TemporaryDirectory(
            prefix="ai_visual_composer_studio_montage_"
        ) as directory:
            principal_path = Path(directory) / "montage-principal.mp4"
            montage_result = montage_service.compose(
                plan=montage_plan,
                output_path=principal_path,
                profile=profile,
            )
            preparation = StudioPreparation(
                profile_key=montage_plan.profile_key,
                profile=profile,
                subtitle_profile=None,
                video_path=montage_result.output_path,
                subtitle_path=None,
                input_mode=StudioInputMode.VIDEO.value,
                subtitles_enabled=False,
            )
            render_result = self.render_prepared(
                preparation=preparation,
                project=project,
                music_path=music_path,
                intro_outro_selection=intro_outro_selection,
                output_path=output_path,
                render_service=render_service,
            )
        return StudioMontageRenderResult(
            montage_result=montage_result,
            render_result=render_result,
        )

    @staticmethod
    def persist_subtitle_base(subtitle_path, output_path):
        """Publish an immutable canonical SRT beside the project output."""
        output_path = Path(output_path)
        target_path = (
            output_path.parent.parent
            / "subtitles"
            / f"{output_path.stem}.srt"
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(subtitle_path, target_path)
        return target_path

    @staticmethod
    def persist_render_subtitle(
        base_subtitle_path,
        output_path,
        subtitle_profile,
        render_fps,
        timing=None,
        original=False,
    ):
        """Publish the derived SRT used exclusively by the renderer."""
        if original:
            content = Path(base_subtitle_path).read_text(encoding="utf-8")
            text_case = TextCasePolicy.from_cue_policy(
                subtitle_profile.cue_policy
            )
            rendered = text_case.apply_srt_cues(content)
            if rendered == content:
                return Path(base_subtitle_path)
            target_path = (
                Path(output_path).parent.parent
                / "subtitles"
                / f"{Path(output_path).stem}_original.srt"
            )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = target_path.with_suffix(".srt.tmp")
            temporary_path.write_text(rendered, encoding="utf-8")
            temporary_path.replace(target_path)
            return target_path

        mode = CueModelRegistry.mode_from(subtitle_profile.cue_policy)
        output_path = Path(output_path)
        target_path = (
            output_path.parent.parent
            / "subtitles"
            / f"{output_path.stem}_{mode}.srt"
        )
        transformed = SubtitleCueTransformer(
            subtitle_profile=subtitle_profile,
            render_fps=render_fps,
        ).transform(
            Path(base_subtitle_path).read_text(encoding="utf-8"),
            timing=timing,
        )
        if not transformed.strip():
            raise ValueError("El SRT de STUDIO no produjo cues renderizables.")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = target_path.with_suffix(".srt.tmp")
        temporary_path.write_text(transformed, encoding="utf-8")
        temporary_path.replace(target_path)
        return target_path

    @staticmethod
    def with_subtitle_artifacts(
        rendered,
        base_subtitle_path,
        render_subtitle_path,
        subtitle_preparation_duration=None,
    ):
        """Attach standard STUDIO subtitle artifacts to render results."""
        if not isinstance(rendered, StudioRenderResult):
            return rendered
        return replace(
            rendered,
            generated_subtitle_path=Path(render_subtitle_path),
            base_subtitle_path=Path(base_subtitle_path),
            subtitle_preparation_duration=subtitle_preparation_duration,
        )
