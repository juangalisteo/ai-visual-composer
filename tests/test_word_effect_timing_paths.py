"""Word effects keep their per-word timing on every subtitle route.

SOLO VIDEO already passes Whisper word times to the ASS renderer. These tests
cover the other routes: GUION/IMAGEN/VIDEO pass the Whisper times saved next
to the SRT, and SRT + VIDEO and VIDEO + AUDIO | SRT spread each cue over its
words (approximate times, render only). The saved SRT files never change.
"""

import json
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.modules.studio.execution_coordinator import StudioExecutionCoordinator
from app.modules.studio.render_service import StudioRenderService
from app.modules.studio.video_audio_srt import (
    StudioVideoAudioSrtPlan,
    StudioVideoAudioSrtService,
)
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
    approximate_word_timings,
    whisper_timing_path,
)
from app.modules.video.config.loaders.subtitle_loader import SubtitleConfigLoader
from app.modules.video.video_build_context import (
    VideoBuildComponents,
    VideoBuildContext,
)
from app.modules.video.video_build_context_factory import VideoBuildContextFactory
from app.modules.video.video_filter_context_factory import VideoFilterContextFactory
from app.modules.video.subtitles.subtitle_render_preparation import (
    SubtitleRenderPreparation,
)
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


SRT = (
    "1\n00:00:00,000 --> 00:00:01,500\nUNO DOS TRES\n\n"
    "2\n00:00:02,000 --> 00:00:03,000\nHOLA MUNDO\n"
)
CUES = ((0, 1500, "UNO DOS TRES"), (2000, 3000, "HOLA MUNDO"))
DIALOGUE = re.compile(
    r"^Dialogue: \d+,(\d+):(\d{2}):(\d{2})\.(\d{2}),"
    r"(\d+):(\d{2}):(\d{2})\.(\d{2}),"
)


def _subtitle_profile(component, effect, family="minimalista"):
    return SubtitleProfileResolver().load(
        SubtitleProfileKey(
            component=component,
            platform="vertical",
            family=family,
            profile_id=f"subtitulo_{component.value}_vertical_{effect}",
        )
    )


def _whisper_timing():
    words = (
        ("uno", 0.1, 0.4), ("dos", 0.5, 0.9), ("tres", 1.0, 1.5),
        ("hola", 2.0, 2.3), ("mundo", 2.6, 3.0),
    )
    return SubtitleTiming(
        source="whisper",
        segments=(
            SpeechSegment(
                start=0.1,
                end=3.0,
                words=tuple(WordTiming(*word) for word in words),
            ),
        ),
    )


def _dialogue_intervals(ass):
    intervals = []
    for line in ass.splitlines():
        match = DIALOGUE.match(line)
        if match:
            h1, m1, s1, c1, h2, m2, s2, c2 = map(int, match.groups())
            intervals.append(
                (
                    ((h1 * 60 + m1) * 60 + s1) * 1000 + c1 * 10,
                    ((h2 * 60 + m2) * 60 + s2) * 1000 + c2 * 10,
                    line,
                )
            )
    return intervals


def _assert_word_intervals_inside_cues(ass, words_per_cue=(3, 2)):
    intervals = _dialogue_intervals(ass)
    for (cue_start, cue_end, text), word_count in zip(CUES, words_per_cue):
        inside = [
            interval for interval in intervals
            if cue_start <= interval[0] < cue_end
        ]
        assert len(inside) == word_count, text
        assert inside[0][0] == cue_start
        assert inside[-1][1] == cue_end
        assert all(
            cue_start <= start < end <= cue_end
            for start, end, _ in inside
        )
    return intervals


def _studio_profile():
    return SimpleNamespace(
        width=1080,
        height=1920,
        fps=30,
        pixel_format="yuv420p",
        audio_sample_rate=48_000,
        codec="libx264",
        preset="medium",
        crf=18,
        audio_codec="aac",
        audio_bitrate="192k",
        audio_channels=2,
        movflags="+faststart",
    )


class _CapturingRunner:
    """Keeps the subtitle filter and the ASS text FFmpeg would read."""

    def __init__(self):
        self.ass = []
        self.graphs = []

    def run(self, command):
        graph = command[command.index("-filter_complex") + 1]
        self.graphs.append(graph)
        if "ass='" in graph:
            ass_path = graph.split("ass='")[1].split("':fontsdir", 1)[0]
            ass_path = Path(ass_path.replace(r"\:", ":").replace(r"\'", "'"))
            self.ass.append(ass_path.read_text(encoding="utf-8"))
        Path(command[-1]).write_bytes(b"rendered")


class _Validator:
    def validate(self, output_path, expected_duration, profile):
        assert Path(output_path).is_file()
        return expected_duration


def _run_srt_video(tmp_path, subtitle_profile, srt=SRT):
    source_srt = tmp_path / "input.srt"
    source_srt.write_text(srt, encoding="utf-8")
    video = tmp_path / "input.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "demo" / "video" / "demo.mp4"
    output.parent.mkdir(parents=True)
    runner = _CapturingRunner()
    service = StudioRenderService(
        runner=runner,
        probe=SimpleNamespace(
            inspect=lambda path: SimpleNamespace(duration=3.0, has_audio=True),
        ),
        output_validator=_Validator(),
    )
    service.FONTS_DIRECTORY = tmp_path
    preparation = SimpleNamespace(
        video_path=video,
        subtitle_path=source_srt,
        input_mode="srt_video",
        profile_key=OperationalProfileKey(
            component=ProfileComponent.STUDIO,
            platform="vertical",
            profile_id="studio_vertical",
        ),
        profile=_studio_profile(),
        subtitle_profile=subtitle_profile,
        subtitle_original=True,
    )
    whisper = Mock()
    StudioExecutionCoordinator().render_prepared(
        preparation=preparation,
        project=Mock(),
        music_path=None,
        intro_outro_selection=None,
        output_path=output,
        render_service=service,
        external_subtitle_preparation_service=whisper,
    )
    whisper.prepare.assert_not_called()
    return runner, tmp_path / "demo" / "subtitles"


def _run_video_audio_srt(tmp_path, subtitle_profile):
    source_srt = tmp_path / "input.srt"
    source_srt.write_text(SRT, encoding="utf-8")
    video = tmp_path / "input.mp4"
    audio = tmp_path / "input.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    output = tmp_path / "demo" / "video" / "demo.mp4"
    runner = _CapturingRunner()
    service = StudioVideoAudioSrtService(
        probe=SimpleNamespace(
            inspect=lambda path: SimpleNamespace(duration=3.0),
            get_duration=lambda path: 3.0,
        ),
        runner=runner,
        validator=_Validator(),
    )
    service.FONTS_DIRECTORY = tmp_path
    operational_key = OperationalProfileKey(
        component=ProfileComponent.STUDIO,
        platform="vertical",
        profile_id="studio_vertical",
    )
    config = Mock()
    config.get_operational_profile_key.return_value = operational_key
    config.get_profile_config.return_value = {}
    config.get_subtitle_profile_by_key.return_value = subtitle_profile
    StudioExecutionCoordinator().run_video_audio_srt(
        StudioVideoAudioSrtPlan(
            video_path=video,
            audio_path=audio,
            subtitle_path=source_srt,
        ),
        subtitle_profile_key=subtitle_profile.key,
        project=Mock(),
        config_manager=config,
        profile_loader=Mock(load=Mock(return_value=_studio_profile())),
        output_path_resolver=Mock(resolve=Mock(return_value=output)),
        service=service,
        subtitle_profile_key_normalizer=(
            lambda subtitle_profile_key: subtitle_profile_key
        ),
    )
    return runner, tmp_path / "demo" / "subtitles"


def _guion_filter_context(tmp_path, subtitle_profile, timing):
    subtitle_path = tmp_path / "subtitulos.srt"
    subtitle_path.write_text(SRT, encoding="utf-8")
    config = SimpleNamespace(
        subtitles=SubtitleConfigLoader().load_render_style(
            subtitle_profile.render_style
        ),
        width=1080,
        height=1920,
        subtitle_style=subtitle_profile.render_style,
        subtitle_cue_policy=subtitle_profile.cue_policy,
    )
    context = VideoBuildContext(
        config=config,
        media=SimpleNamespace(image_paths=(Path("a.png"),)),
        timeline=SimpleNamespace(subtitle_path=subtitle_path),
        subtitle_timing=timing,
    )
    components = VideoBuildComponents(
        motion_builder=object(),
        transition_builder=object(),
        overlay_builder=SimpleNamespace(inputs=()),
        visual_effect_builder=SimpleNamespace(inputs=()),
    )
    return VideoFilterContextFactory().build(
        build_context=context,
        components=components,
    )


def _guion_ass(tmp_path, subtitle_profile, timing):
    filter_context = _guion_filter_context(tmp_path, subtitle_profile, timing)
    try:
        return Path(filter_context.subtitle_path).read_text(encoding="utf-8")
    finally:
        Path(filter_context.temporary_subtitle_path).unlink()


# --- approximate_word_timings ---------------------------------------------


def test_approximate_word_timings_spreads_the_cue_by_characters():
    words = approximate_word_timings(1.0, 2.0, ("UNO", "DOS", "TRES"))

    assert [word.text for word in words] == ["UNO", "DOS", "TRES"]
    assert words[0].start == 1.0
    assert words[-1].end == 2.0
    assert [word.end for word in words[:-1]] == [
        word.start for word in words[1:]
    ]
    assert words[0].end == pytest.approx(1.3)
    assert words[1].end == pytest.approx(1.6)
    assert all(word.source == "approximate" for word in words)


def test_approximate_word_timings_without_words_is_empty():
    assert approximate_word_timings(0.0, 1.0, ()) == ()
    assert approximate_word_timings(0.0, 1.0, ("", " ")) == ()


# --- GUION / IMAGEN / VIDEO -----------------------------------------------


def test_guion_context_carries_the_whisper_times_saved_beside_the_srt(tmp_path):
    subtitle_path = tmp_path / "subtitulos.srt"
    subtitle_path.write_text(SRT, encoding="utf-8")
    whisper_timing_path(subtitle_path).write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start": 0.1,
                        "end": 0.9,
                        "words": [
                            {"word": " uno", "start": 0.1, "end": 0.4},
                            {"word": " dos", "start": 0.5, "end": 0.9},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    media = SimpleNamespace(
        audio_path=Path("audio.mp3"),
        subtitle_path=subtitle_path,
        output_path=Path("out.mp4"),
        image_paths=(Path("one.png"),),
    )
    config = SimpleNamespace(
        subtitle_offset=0.0,
        transitions=SimpleNamespace(duration=0.4),
        width=1080,
        height=1920,
        fps=30,
    )
    project = SimpleNamespace(
        subtitle_path=lambda: subtitle_path,
        storyboard_path=lambda: tmp_path / "storyboard.json",
        images_manifest_path=lambda: tmp_path / "images.json",
        video_path=lambda: tmp_path / "out.mp4",
    )
    module = "app.modules.video.video_build_context_factory"

    with patch(f"{module}.AudioResolver"), patch(
        f"{module}.VideoConfigLoader"
    ) as config_loader, patch(f"{module}.MediaLoader") as media_loader, patch(
        f"{module}.TimelineBuilder"
    ) as timeline_builder:
        config_loader.return_value.load.return_value = config
        media_loader.return_value.load.return_value = media
        timeline_builder.return_value.build.return_value = SimpleNamespace(
            audio_duration=3.0,
            image_duration=3.0,
        )
        with_subtitles = VideoBuildContextFactory(project=project).build()
        without_subtitles = VideoBuildContextFactory(project=project).build(
            render_subtitles=False,
        )

    assert [
        (word.text, word.start, word.end)
        for word in with_subtitles.subtitle_timing.words
    ] == [("uno", 0.1, 0.4), ("dos", 0.5, 0.9)]
    assert without_subtitles.subtitle_timing is None


def test_guion_context_without_whisper_times_carries_none(tmp_path):
    subtitle_path = tmp_path / "subtitulos.srt"
    subtitle_path.write_text(SRT, encoding="utf-8")
    module = "app.modules.video.video_build_context_factory"
    project = SimpleNamespace(
        subtitle_path=lambda: subtitle_path,
        storyboard_path=lambda: tmp_path / "storyboard.json",
        images_manifest_path=lambda: tmp_path / "images.json",
        video_path=lambda: tmp_path / "out.mp4",
    )

    with patch(f"{module}.AudioResolver"), patch(
        f"{module}.VideoConfigLoader"
    ) as config_loader, patch(f"{module}.MediaLoader") as media_loader, patch(
        f"{module}.TimelineBuilder"
    ) as timeline_builder:
        config_loader.return_value.load.return_value = SimpleNamespace(
            subtitle_offset=0.0,
            transitions=SimpleNamespace(duration=0.4),
            width=1080,
            height=1920,
            fps=30,
        )
        media_loader.return_value.load.return_value = SimpleNamespace(
            audio_path=Path("audio.mp3"),
            subtitle_path=subtitle_path,
            image_paths=(Path("one.png"),),
        )
        timeline_builder.return_value.build.return_value = SimpleNamespace(
            audio_duration=3.0,
            image_duration=3.0,
        )
        context = VideoBuildContextFactory(project=project).build()

    assert context.subtitle_timing is None


@pytest.mark.parametrize(
    "component",
    (ProfileComponent.GUION, ProfileComponent.IMAGEN, ProfileComponent.VIDEO),
)
def test_guion_renders_word_effects_with_the_whisper_times(tmp_path, component):
    profile = _subtitle_profile(component, "highlight_in_sentence")

    ass = _guion_ass(tmp_path, profile, _whisper_timing())

    intervals = _dialogue_intervals(ass)
    active = [
        (start, end) for start, end, line in intervals
        if r"{\1c&H0000FFFF}" in line
    ]
    assert active == [
        (100, 400), (500, 900), (1000, 1500), (2000, 2300), (2600, 3000),
    ]
    _assert_word_intervals_inside_cues(ass, words_per_cue=(6, 3))


@pytest.mark.parametrize(
    "component",
    (ProfileComponent.GUION, ProfileComponent.IMAGEN, ProfileComponent.VIDEO),
)
def test_guion_karaoke_uses_the_whisper_times(tmp_path, component):
    profile = _subtitle_profile(component, "continuous_karaoke", "karaoke")

    ass = _guion_ass(tmp_path, profile, _whisper_timing())

    # Leading gap of 0.1 s, then each word lasts what Whisper says.
    assert (
        r"{\k10}{\kf10}U{\kf20}NO{\k10} {\kf40}DOS{\k10} {\kf50}TRES" in ass
    )
    assert r"{\kf15}HO{\kf15}LA{\k30} {\kf24}MUN{\kf16}DO" in ass


def test_guion_cue_that_does_not_match_whisper_gets_approximate_times(tmp_path):
    profile = _subtitle_profile(ProfileComponent.GUION, "highlight_in_sentence")
    timing = _whisper_timing()
    # The script says "DOS" where Whisper heard "dios": only that cue changes.
    words = list(timing.words)
    words[1] = WordTiming("dios", 0.5, 0.9)
    timing = SubtitleTiming(
        source="whisper",
        segments=(SpeechSegment(start=0.1, end=3.0, words=tuple(words)),),
    )

    ass = _guion_ass(tmp_path, profile, timing)

    intervals = _assert_word_intervals_inside_cues(ass, words_per_cue=(3, 3))
    assert [(start, end) for start, end, _ in intervals[:3]] == [
        (0, 450), (450, 900), (900, 1500),
    ]
    assert [(start, end) for start, end, _ in intervals[3:]] == [
        (2000, 2300), (2300, 2600), (2600, 3000),
    ]


def test_guion_without_whisper_times_gets_approximate_times(tmp_path):
    profile = _subtitle_profile(ProfileComponent.GUION, "highlight_in_sentence")

    ass = _guion_ass(tmp_path, profile, None)

    _assert_word_intervals_inside_cues(ass)


# --- SRT + VIDEO ----------------------------------------------------------


@pytest.mark.parametrize(
    ("effect", "family", "marker"),
    (
        ("continuous_karaoke", "karaoke", r"\kf"),
        ("typewriter", "minimalista", "_"),
        ("highlight_in_sentence", "minimalista", r"{\1c&H0000FFFF}"),
        ("active_pill", "minimalista", r"\p1"),
        ("pop_in_sentence", "minimalista", r"\fscx125"),
        ("alpha_fade", "minimalista", r"\1a&HFF&"),
    ),
)
def test_srt_video_renders_word_effects_without_whisper(
    tmp_path, effect, family, marker,
):
    profile = _subtitle_profile(ProfileComponent.STUDIO, effect, family)

    runner, _ = _run_srt_video(tmp_path, profile)

    (ass,) = runner.ass
    intervals = _dialogue_intervals(ass)
    for cue_start, cue_end, _ in CUES:
        inside = [
            (start, end) for start, end, line in intervals
            if cue_start <= start < cue_end
        ]
        assert any(
            marker in line for start, _, line in intervals
            if cue_start <= start < cue_end
        )
        assert min(start for start, _ in inside) == cue_start
        assert max(end for _, end in inside) == cue_end
        assert all(cue_start <= start < end <= cue_end for start, end in inside)


def test_srt_video_highlight_gives_each_word_a_slot_inside_its_cue(tmp_path):
    profile = _subtitle_profile(ProfileComponent.STUDIO, "highlight_in_sentence")

    runner, _ = _run_srt_video(tmp_path, profile)

    intervals = _assert_word_intervals_inside_cues(runner.ass[0])
    assert [(start, end) for start, end, _ in intervals] == [
        (0, 450), (450, 900), (900, 1500), (2000, 2440), (2440, 3000),
    ]


def test_srt_video_karaoke_spreads_each_cue_over_its_words(tmp_path):
    profile = _subtitle_profile(
        ProfileComponent.STUDIO, "continuous_karaoke", "karaoke",
    )

    runner, _ = _run_srt_video(tmp_path, profile)

    lines = [line for _, _, line in _dialogue_intervals(runner.ass[0])]
    assert lines[0].startswith("Dialogue: 0,0:00:00.00,0:00:01.50,")
    assert lines[0].endswith(r"{\kf15}U{\kf30}NO {\kf45}DOS {\kf60}TRES")
    assert lines[1].startswith("Dialogue: 0,0:00:02.00,0:00:03.00,")
    assert lines[1].endswith(r"{\kf22}HO{\kf22}LA {\kf34}MUN{\kf22}DO")


@pytest.mark.parametrize(
    ("effect", "family"),
    (
        ("continuous_karaoke", "karaoke"),
        ("highlight_in_sentence", "minimalista"),
    ),
)
def test_srt_video_saved_srt_files_are_unchanged(tmp_path, effect, family):
    profile = _subtitle_profile(ProfileComponent.STUDIO, effect, family)
    srt = SRT.replace("UNO DOS TRES", "Uno, dos, tres.").replace(
        "HOLA MUNDO", "Hola mundo",
    )

    _, subtitles = _run_srt_video(tmp_path, profile, srt)

    assert (subtitles / "demo.srt").read_bytes() == (
        tmp_path / "input.srt"
    ).read_bytes()
    original = subtitles / "demo_original.srt"
    if profile.cue_policy.get("text_case") == "original":
        assert not original.exists()
    else:
        # Upper case is the only change, as before; times and lines stay.
        assert original.read_text(encoding="utf-8") == srt.upper()
    assert sorted(path.name for path in subtitles.iterdir()) == sorted(
        ["demo.srt"]
        + (["demo_original.srt"] if original.exists() else [])
    )


def test_srt_video_profile_without_word_effect_renders_as_before(tmp_path):
    profile = _subtitle_profile(ProfileComponent.STUDIO, "palabra_por_palabra", "estandar")

    runner, subtitles = _run_srt_video(tmp_path, profile)

    assert runner.ass == []
    (graph,) = runner.graphs
    assert "subtitles=" in graph
    assert "demo.srt" in graph
    assert (subtitles / "demo.srt").read_text(encoding="utf-8") == SRT


# --- VIDEO + AUDIO | SRT --------------------------------------------------


@pytest.mark.parametrize(
    ("effect", "family", "marker"),
    (
        ("continuous_karaoke", "karaoke", r"\kf"),
        ("highlight_in_sentence", "minimalista", r"{\1c&H0000FFFF}"),
    ),
)
def test_video_audio_srt_renders_word_effects(tmp_path, effect, family, marker):
    profile = _subtitle_profile(ProfileComponent.STUDIO, effect, family)

    runner, subtitles = _run_video_audio_srt(tmp_path, profile)

    (ass,) = runner.ass
    intervals = _dialogue_intervals(ass)
    assert all(marker in line for _, _, line in intervals)
    for cue_start, cue_end, _ in CUES:
        inside = [
            (start, end) for start, end, _ in intervals
            if cue_start <= start < cue_end
        ]
        assert min(start for start, _ in inside) == cue_start
        assert max(end for _, end in inside) == cue_end
    if effect == "highlight_in_sentence":
        _assert_word_intervals_inside_cues(ass)
    assert (subtitles / "demo.srt").read_bytes() == (
        tmp_path / "input.srt"
    ).read_bytes()


# --- Profiles without word effects ----------------------------------------


@pytest.mark.parametrize(
    ("component", "effect", "family"),
    (
        (ProfileComponent.STUDIO, "gravity_drop", "minimalista"),
        (ProfileComponent.STUDIO, "roll_up", "karaoke"),
        (ProfileComponent.GUION, "gravity_drop", "minimalista"),
    ),
)
def test_dynamic_profile_without_word_effect_ignores_word_times(
    tmp_path, component, effect, family,
):
    profile = _subtitle_profile(component, effect, family)
    source = tmp_path / "source.srt"
    source.write_text(SRT, encoding="utf-8")
    style = SubtitleConfigLoader().load_render_style(profile.render_style)

    rendered = []
    for timing in (None, _whisper_timing()):
        prepared = SubtitleRenderPreparation().prepare(
            source, style, 1080, 1920, profile.render_style,
            timing=timing, cue_policy=profile.cue_policy,
        )
        try:
            rendered.append(prepared.path.read_text(encoding="utf-8"))
        finally:
            prepared.cleanup()

    assert rendered[0] == rendered[1]
