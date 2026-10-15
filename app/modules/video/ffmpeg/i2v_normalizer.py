class I2VClipTransform:
    """Pure I2V normalization graph fragment for the final FFmpeg render."""

    def build_filter(
        self,
        source_frame_count,
        duration,
        width,
        height,
        fps,
        pixel_format,
        input_stream,
        output_stream,
        label_prefix,
    ):
        source_frame_count = max(1, int(source_frame_count))
        labels = self._labels(label_prefix)
        parts = [
            f"{input_stream}trim=start_frame=0:"
            f"end_frame={source_frame_count},"
            f"setpts=PTS-STARTPTS[{labels['source']}]"
        ]

        if source_frame_count > 2:
            reverse_frame_count = source_frame_count - 2
            period_frame_count = (
                source_frame_count + reverse_frame_count
            )
            parts.extend([
                f"[{labels['source']}]split=2"
                f"[{labels['forward']}][{labels['reverse_source']}]",
                f"[{labels['reverse_source']}]reverse,"
                "trim=start_frame=1:"
                f"end_frame={source_frame_count - 1},"
                f"setpts=PTS-STARTPTS[{labels['reverse_trimmed']}]",
                f"[{labels['forward']}][{labels['reverse_trimmed']}]"
                f"concat=n=2:v=1:a=0[{labels['pingpong_period']}]",
                f"[{labels['pingpong_period']}]loop=loop=-1:"
                f"size={period_frame_count}:start=0,"
                f"trim=duration={duration:.6f},"
                f"setpts=PTS-STARTPTS[{labels['looped']}]",
            ])
        else:
            parts.append(
                f"[{labels['source']}]loop=loop=-1:"
                f"size={source_frame_count}:start=0,"
                f"trim=duration={duration:.6f},"
                f"setpts=PTS-STARTPTS[{labels['looped']}]"
            )

        parts.append(
            f"[{labels['looped']}]"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps},"
            f"format={pixel_format},"
            "setsar=1,"
            "settb=AVTB,"
            f"setpts=PTS-STARTPTS{output_stream}"
        )
        return ";".join(parts)

    def _labels(self, label_prefix):
        prefix = str(label_prefix)
        return {
            "source": f"{prefix}_source",
            "forward": f"{prefix}_forward",
            "reverse_source": f"{prefix}_reverse_source",
            "reverse_trimmed": f"{prefix}_reverse_trimmed",
            "pingpong_period": f"{prefix}_pingpong_period",
            "looped": f"{prefix}_looped",
        }
