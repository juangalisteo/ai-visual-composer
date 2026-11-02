"""Selección de planes de montaje STUDIO."""

from app.modules.studio import (
    StudioInputMode,
    StudioMontageInputError,
    to_studio_operational_error,
)


class StudioMontageSelection:
    def __init__(self, planning_service, terminal, on_cancel=None):
        self._planning_service = planning_service
        self._terminal = terminal
        self._on_cancel = on_cancel

    @staticmethod
    def _write(message, writer):
        (writer or (lambda value: None))(message)

    def select_plan(
        self,
        profile_key,
        profile,
        select_order,
        select_transitions,
        writer=None,
    ):
        """Report missing clips as an input error; the order prompt retries."""
        try:
            return self._select_plan(
                profile_key,
                profile,
                select_order,
                select_transitions,
                writer,
            )
        except StudioMontageInputError as error:
            raise to_studio_operational_error(
                error,
                mode=StudioInputMode.MONTAJE_VIDEOS.value,
                recommended_action=(
                    "Pon en esa carpeta dos o más vídeos .mp4 y vuelve a "
                    "intentarlo."
                ),
            ) from error

    def _select_plan(
        self,
        profile_key,
        profile,
        select_order,
        select_transitions,
        writer,
    ):
        candidates = self._planning_service.discover(profile)
        self._write("\nVÍDEOS ENCONTRADOS\n", writer)
        for clip in candidates.clips:
            self._write(f"[{clip.temporary_id}] {clip.original_name}", writer)

        clips = select_order(candidates)
        transitions_enabled = select_transitions()
        return self._planning_service.create_plan(
            profile_key=profile_key,
            transitions_enabled=transitions_enabled,
            clips=clips,
        )

    def select_order(self, candidates, writer=None):
        self._write("\nIntroduce el orden de montaje:", writer)
        while True:
            answer = self._terminal.read("\n> ")
            if str(answer or "").strip() == "0" and self._on_cancel is not None:
                self._on_cancel()
            try:
                return self._planning_service.parse_order(
                    answer,
                    candidates,
                )
            except StudioMontageInputError as error:
                self._write(f"\n{error}", writer)
