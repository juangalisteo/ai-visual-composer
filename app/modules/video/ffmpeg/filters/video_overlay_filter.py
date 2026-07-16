class VideoOverlayFilter:

    def build(
        self,
        base_stream,
        overlay_stream,
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

        if blend_mode == "screen":

            blend = (
                "blend="
                "all_mode=screen:"
                f"all_opacity={opacity}"
            )

            return (
                f"[{base_stream}]"
                f"[{overlay_stream}]"
                f"{blend}:"
                f"enable='{enable}'"
                f"[{output_stream}]"
            )

        if blend_mode == "add":

            blend = (
                "blend="
                "all_mode=addition:"
                f"all_opacity={opacity}"
            )

            return (
                f"[{base_stream}]"
                f"[{overlay_stream}]"
                f"{blend}:"
                f"enable='{enable}'"
                f"[{output_stream}]"
            )

        if blend_mode == "lighten":

            blend = (
                "blend="
                "all_mode=lighten:"
                f"all_opacity={opacity}"
            )

            return (
                f"[{base_stream}]"
                f"[{overlay_stream}]"
                f"{blend}:"
                f"enable='{enable}'"
                f"[{output_stream}]"
            )

        if blend_mode == "overlay":

            blend = (
                "blend="
                "all_mode=overlay:"
                f"all_opacity={opacity}"
            )

            return (
                f"[{base_stream}]"
                f"[{overlay_stream}]"
                f"{blend}:"
                f"enable='{enable}'"
                f"[{output_stream}]"
            )

        raise ValueError(
            f"Modo de mezcla no soportado: "
            f"{blend_mode}"
        )