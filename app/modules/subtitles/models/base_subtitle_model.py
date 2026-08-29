from abc import ABC, abstractmethod


class BaseSubtitleModel(ABC):

    @abstractmethod
    def optimize(self, blocks, timing=None):
        pass
