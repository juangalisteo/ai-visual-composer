from abc import ABC
from abc import abstractmethod

from app.modules.video.ffmpeg.graphs.graph_context import (
    GraphContext
)

from app.modules.video.ffmpeg.graphs.graph_result import (
    GraphResult
)


class BaseGraphBuilder(
    ABC
):

    @abstractmethod
    def build(
        self,
        graph: GraphContext
    ) -> GraphResult:
        """
        Construye una parte del filtro FFmpeg.
        """
        raise NotImplementedError