import time

from app.modules.video.motion.motion_selector import MotionSelector
from app.shared.progress_logger import ProgressLogger


class MotionBuilder:

    def __init__(
        self,
        config
    ):
        self.config = config

        self.selector = MotionSelector(
            config
        )

    def build(
        self,
        image_index,
        image_count,
        image_path,
        duration,
        width,
        height,
        fps
    ):
        start = time.perf_counter()

        if duration is None:
            raise ValueError(
                "MotionBuilder necesita la duración "
                "real de la imagen."
            )

        duration = float(
            duration
        )

        width = int(
            width
        )

        height = int(
            height
        )

        fps = int(
            fps
        )

        if duration <= 0:
            raise ValueError(
                "La duración de la imagen debe ser "
                "superior a cero."
            )

        if width <= 0 or height <= 0:
            raise ValueError(
                "Las dimensiones deben ser "
                "superiores a cero."
            )

        if fps <= 0:
            raise ValueError(
                "Los FPS deben ser superiores a cero."
            )

        frame_count = max(
            2,
            round(
                duration
                * fps
            )
        )

        if not self.config.enabled:
            motion_type = "none"

            motion_filter = self._default_filter(
                width=width,
                height=height,
                fps=fps,
                frame_count=frame_count
            )

        else:
            motion_type = self.selector.select(
                image_index=image_index,
                image_count=image_count
            )

            builders = {
                "zoom_in": self._zoom_in,
                "zoom_out": self._zoom_out,
                "pan_left": self._pan_left,
                "pan_right": self._pan_right,
                "pan_up": self._pan_up,
                "pan_down": self._pan_down
            }

            builder = builders.get(
                motion_type,
                self._default_filter
            )

            motion_filter = builder(
                width=width,
                height=height,
                fps=fps,
                frame_count=frame_count
            )

        elapsed = (
            time.perf_counter()
            - start
        )

        ProgressLogger.detail(
            f"Movimiento escena {image_index + 1}: "
            f"{motion_type} | "
            f"{duration:.2f} s | "
            f"{frame_count} fotogramas | "
            f"{elapsed:.4f} s"
        )

        return {
            "type": motion_type,
            "filter": motion_filter,
            "duration": duration,
            "frame_count": frame_count
        }

    def _zoom_in(
        self,
        width,
        height,
        fps,
        frame_count
    ):
        progress = self._progress_expression(
            frame_count
        )

        base_zoom = self.config.base_zoom
        zoom_amount = self.config.zoom_amount

        return (
            self._internal_scale(
                width,
                height
            )
            + ","
            + "zoompan="
            + f"z='1+{base_zoom}+"
            + f"{zoom_amount}*({progress})':"
            + "x='iw/2-(iw/zoom/2)':"
            + "y='ih/2-(ih/zoom/2)':"
            + "d=1:"
            + f"s={self._internal_width(width)}x"
            + f"{self._internal_height(height)}:"
            + f"fps={fps},"
            + f"scale={width}:{height}:flags=lanczos"
        )

    def _zoom_out(
        self,
        width,
        height,
        fps,
        frame_count
    ):
        progress = self._progress_expression(
            frame_count
        )

        base_zoom = self.config.base_zoom
        zoom_amount = self.config.zoom_amount

        maximum_zoom = (
            1.0
            + base_zoom
            + zoom_amount
        )

        return (
            self._internal_scale(
                width,
                height
            )
            + ","
            + "zoompan="
            + f"z='{maximum_zoom}-"
            + f"{zoom_amount}*({progress})':"
            + "x='iw/2-(iw/zoom/2)':"
            + "y='ih/2-(ih/zoom/2)':"
            + "d=1:"
            + f"s={self._internal_width(width)}x"
            + f"{self._internal_height(height)}:"
            + f"fps={fps},"
            + f"scale={width}:{height}:flags=lanczos"
        )

    def _pan_left(
        self,
        width,
        height,
        fps,
        frame_count
    ):
        progress = self._progress_expression(
            frame_count
        )

        zoom = self._pan_zoom_expression(
            progress
        )

        return (
            self._internal_scale(
                width,
                height
            )
            + ","
            + "zoompan="
            + f"z='{zoom}':"
            + f"x='(iw-iw/zoom)*(1-({progress}))':"
            + "y='ih/2-(ih/zoom/2)':"
            + "d=1:"
            + f"s={self._internal_width(width)}x"
            + f"{self._internal_height(height)}:"
            + f"fps={fps},"
            + f"scale={width}:{height}:flags=lanczos"
        )

    def _pan_right(
        self,
        width,
        height,
        fps,
        frame_count
    ):
        progress = self._progress_expression(
            frame_count
        )

        zoom = self._pan_zoom_expression(
            progress
        )

        return (
            self._internal_scale(
                width,
                height
            )
            + ","
            + "zoompan="
            + f"z='{zoom}':"
            + f"x='(iw-iw/zoom)*({progress})':"
            + "y='ih/2-(ih/zoom/2)':"
            + "d=1:"
            + f"s={self._internal_width(width)}x"
            + f"{self._internal_height(height)}:"
            + f"fps={fps},"
            + f"scale={width}:{height}:flags=lanczos"
        )

    def _pan_up(
        self,
        width,
        height,
        fps,
        frame_count
    ):
        progress = self._progress_expression(
            frame_count
        )

        zoom = self._pan_zoom_expression(
            progress
        )

        return (
            self._internal_scale(
                width,
                height
            )
            + ","
            + "zoompan="
            + f"z='{zoom}':"
            + "x='iw/2-(iw/zoom/2)':"
            + f"y='(ih-ih/zoom)*(1-({progress}))':"
            + "d=1:"
            + f"s={self._internal_width(width)}x"
            + f"{self._internal_height(height)}:"
            + f"fps={fps},"
            + f"scale={width}:{height}:flags=lanczos"
        )

    def _pan_down(
        self,
        width,
        height,
        fps,
        frame_count
    ):
        progress = self._progress_expression(
            frame_count
        )

        zoom = self._pan_zoom_expression(
            progress
        )

        return (
            self._internal_scale(
                width,
                height
            )
            + ","
            + "zoompan="
            + f"z='{zoom}':"
            + "x='iw/2-(iw/zoom/2)':"
            + f"y='(ih-ih/zoom)*({progress})':"
            + "d=1:"
            + f"s={self._internal_width(width)}x"
            + f"{self._internal_height(height)}:"
            + f"fps={fps},"
            + f"scale={width}:{height}:flags=lanczos"
        )

    def _pan_zoom_expression(
        self,
        progress
    ):
        base_zoom = self.config.base_zoom
        zoom_amount = self.config.zoom_amount

        maximum_zoom = (
            base_zoom
            + zoom_amount
        )

        if not self.config.pan_zoom_enabled:
            return str(
                1.0
                + maximum_zoom
            )

        pan_zoom_start = max(
            base_zoom,
            self.config.pan_zoom_start
        )

        pan_zoom_start = min(
            pan_zoom_start,
            maximum_zoom
        )

        pan_zoom_range = (
            maximum_zoom
            - pan_zoom_start
        )

        return (
            f"1+{pan_zoom_start}+"
            f"{pan_zoom_range}*({progress})"
        )

    def _default_filter(
        self,
        width,
        height,
        fps,
        frame_count
    ):
        return (
            self._base_scale(
                width,
                height
            )
            + ","
            + f"fps={fps}"
        )

    def _progress_expression(
        self,
        frame_count
    ):
        divisor = max(
            1,
            frame_count - 1
        )

        return (
            f"(1-cos(PI*min(on/{divisor},1)))/2"
        )

    def _internal_scale(
        self,
        width,
        height
    ):
        internal_width = self._internal_width(
            width
        )

        internal_height = self._internal_height(
            height
        )

        return (
            f"scale={internal_width}:"
            f"{internal_height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={internal_width}:"
            f"{internal_height},"
            "format=yuv444p"
        )

    def _base_scale(
        self,
        width,
        height
    ):
        return (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )

    def _internal_width(
        self,
        width
    ):
        return (
            int(width)
            * self.config.internal_scale
        )

    def _internal_height(
        self,
        height
    ):
        return (
            int(height)
            * self.config.internal_scale
        )