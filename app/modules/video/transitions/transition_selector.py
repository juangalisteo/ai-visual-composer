import random


class TransitionSelector:

    def __init__(
        self,
        config
    ):
        self.config = config

        self._last_transition = None

    def select(
        self,
        scene_index,
        scene_count
    ):
        if scene_count <= 1:
            return "none"

        if scene_index <= 0:
            return "none"

        if self.config.selection == "sequence":
            return self._select_sequence(
                scene_index
            )

        if self.config.selection == "random":
            return self._select_random()

        raise ValueError(
            f"Modo de selección no soportado: "
            f"{self.config.selection}"
        )

    def _select_sequence(
        self,
        scene_index
    ):
        transitions = (
            self.config.types
        )

        transition = transitions[
            (scene_index - 1)
            % len(transitions)
        ]

        self._last_transition = (
            transition
        )

        return transition

    def _select_random(
        self
    ):
        transitions = list(
            self.config.types
        )

        if (
            self.config.avoid_repeats
            and self._last_transition
            in transitions
            and len(transitions) > 1
        ):
            transitions.remove(
                self._last_transition
            )

        weights = [
            self.config.weights.get(
                transition,
                1.0
            )
            for transition in transitions
        ]

        transition = random.choices(
            population=transitions,
            weights=weights,
            k=1
        )[0]

        self._last_transition = (
            transition
        )

        return transition