from app.modules.video.ffmpeg.command_plan import CommandPlanBuilder


class CommandBuilder:

    def build(
        self,
        images,
        audio_path,
        output_path,
        filter_complex,
        codec,
        preset,
        crf,
        fps,
        pixel_format,
        audio_codec,
        audio_bitrate,
        movflags,
        audio_duration,
        transition_duration,
        media_types=(),
        overlay_inputs=(),
        visual_effect_inputs=(),
        overlay_loop_file=True,
        visual_effect_loop_file=True
    ):
        plan = CommandPlanBuilder().build(
            images=images,
            audio_path=audio_path,
            output_path=output_path,
            filter_complex=filter_complex,
            codec=codec,
            preset=preset,
            crf=crf,
            fps=fps,
            pixel_format=pixel_format,
            audio_codec=audio_codec,
            audio_bitrate=audio_bitrate,
            movflags=movflags,
            audio_duration=audio_duration,
            transition_duration=transition_duration,
            media_types=media_types,
            overlay_inputs=overlay_inputs,
            visual_effect_inputs=visual_effect_inputs,
            overlay_loop_file=overlay_loop_file,
            visual_effect_loop_file=visual_effect_loop_file
        )

        return self._serialize(
            plan
        )

    def _serialize(
        self,
        plan
    ):
        command = [
            "ffmpeg",
            "-y"
        ]

        for input_plan in plan.inputs:
            command.extend(
                input_plan.arguments
            )

        output = (
            plan.output_options
        )

        command.extend([
            "-filter_complex",
            output.filter_complex,

            "-map",
            "[vout]",

            "-map",
            f"{output.audio_index}:a",

            "-t",
            f"{output.audio_duration:.6f}",

            "-c:v",
            output.codec,

            "-preset",
            output.preset,

            "-crf",
            str(
                output.crf
            ),

            "-r",
            str(
                output.fps
            ),

            "-c:a",
            output.audio_codec,

            "-b:a",
            output.audio_bitrate,

            "-pix_fmt",
            output.pixel_format,

            "-movflags",
            output.movflags,

            str(
                output.output_path
            )
        ])

        return command
