"""Central registry for executable subtitle cue capabilities."""

from app.modules.subtitles.modes.acoustic_burst import AcousticBurstModel
from app.modules.subtitles.modes.cumulative_line import CumulativeLineModel
from app.modules.subtitles.modes.rolling_window import RollingWindowModel
from app.modules.subtitles.modes.roll_up import RollUpModel
from app.modules.subtitles.modes.single_line import SingleLineModel
from app.modules.subtitles.modes.three_two_words import ThreeTwoWordsModel
from app.modules.subtitles.modes.two_lines import TwoLineModel
from app.modules.subtitles.modes.word_by_word import WordByWordModel
from app.shared.config_contract import require_text


class CueModelRegistry:
    """Resolve one declared ``cue_policy.mode`` to its cue-model factory."""

    def __init__(self, factories=None):
        self._factories = dict(
            self.default_factories() if factories is None else factories
        )

    @staticmethod
    def default_factories():
        return {
            "acoustic_burst": AcousticBurstModel,
            "cumulative_line": CumulativeLineModel,
            "rolling_window": RollingWindowModel,
            "roll_up": RollUpModel,
            "single_line": SingleLineModel,
            "three_two_words": ThreeTwoWordsModel,
            "two_lines": TwoLineModel,
            "word_by_word": WordByWordModel,
        }

    @staticmethod
    def mode_from(cue_policy):
        return require_text(cue_policy, "mode", "cue_policy.mode").lower()

    def resolve(self, mode):
        if not isinstance(mode, str) or not mode.strip():
            raise ValueError("cue_policy.mode debe ser texto no vacío.")
        normalized = mode.strip().lower()
        try:
            return self._factories[normalized]
        except KeyError as error:
            raise ValueError(
                "Capacidad de cues no soportada: "
                f"{normalized}"
            ) from error

    def create(self, cue_policy):
        mode = self.mode_from(cue_policy)
        return self.resolve(mode)(cue_policy)
