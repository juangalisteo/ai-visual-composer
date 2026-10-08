"""Selección de planes de montaje STUDIO."""

from app.modules.studio import StudioMontageInputError


class StudioMontageSelection:
    def __init__(self, planning_service, terminal):
        self._planning_service = planning_service
        self._terminal = terminal

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
            try:
                return self._planning_service.parse_order(
                    self._terminal.read("\n> "),
                    candidates,
                )
            except StudioMontageInputError as error:
                self._write(f"\n{error}", writer)
