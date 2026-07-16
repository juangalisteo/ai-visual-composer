class LayerCompositor:

    def prepare_stream(
        self,
        input_index,
        output_stream,
        width,
        height,
        fps,
        start_time,
        duration
    ):
        return (
            f"[{input_index}:v]"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps},"
            "format=rgba,"
            f"trim=duration={duration:.6f},"
            "setpts=PTS-STARTPTS"
            f"+{start_time:.6f}/TB"
            f"{output_stream}"
        )

    def compose(
        self,
        base_stream,
        layer_stream,
        output_stream,
        blend_mode,
        opacity,
        start_time,
        end_time
    ):
        enable = (
            f"between(t,{start_time:.3f},"
            f"{end_time:.3f})"
        )

        if blend_mode == "normal":
            alpha_stream = (
                output_stream.replace(
                    "[",
                    "[alpha_"
                )
            )

            return (
                f"{layer_stream}"
                "colorchannelmixer="
                f"aa={opacity:.3f}"
                f"{alpha_stream};"
                f"{base_stream}"
                f"{alpha_stream}"
                "overlay=0:0:"
                "format=auto:"
                f"enable='{enable}'"
                f"{output_stream}"
            )

        mode_map = {
            "screen": "screen",
            "add": "addition",
            "lighten": "lighten",
            "overlay": "overlay"
        }

        ffmpeg_mode = mode_map.get(
            blend_mode
        )

        if ffmpeg_mode is None:
            raise ValueError(
                "Modo de mezcla no soportado: "
                f"{blend_mode}"
            )

        return (
            f"{base_stream}"
            f"{layer_stream}"
            "blend="
            f"all_mode={ffmpeg_mode}:"
            f"all_opacity={opacity:.3f}:"
            f"enable='{enable}'"
            f"{output_stream}"
        )

    def apply_operation(
        self,
        filter_parts,
        current_stream,
        operation,
        input_index,
        operation_index,
        source_prefix,
        output_prefix,
        width,
        height,
        fps
    ):
        prepared_stream = (
            f"[{source_prefix}{operation_index}]"
        )

        output_stream = (
            f"[{output_prefix}{operation_index}]"
        )

        filter_parts.append(
            self.prepare_stream(
                input_index=input_index,
                output_stream=prepared_stream,
                width=width,
                height=height,
                fps=fps,
                start_time=operation["start_time"],
                duration=(
                    operation["end_time"]
                    - operation["start_time"]
                )
            )
        )

        filter_parts.append(
            self.compose(
                base_stream=current_stream,
                layer_stream=prepared_stream,
                output_stream=output_stream,
                blend_mode=operation["blend_mode"],
                opacity=operation["opacity"],
                start_time=operation["start_time"],
                end_time=operation["end_time"]
            )
        )

        return (
            output_stream,
            prepared_stream
        )
