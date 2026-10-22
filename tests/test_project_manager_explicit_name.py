from app.managers.project_manager import ProjectManager
from app.modules.audio.audio_mixer import AudioMixer
from unittest.mock import patch


def test_explicit_project_name_is_sanitized_into_its_output_folder():
    project = ProjectManager(project_name="  request/project  ")

    assert project.project_name == "requestproject"
    assert project.base_path.as_posix() == "output/requestproject"


def test_audio_mixer_with_explicit_artifacts_does_not_construct_legacy_project(
    tmp_path,
):
    voice_path = tmp_path / "voz.mp3"
    output_path = tmp_path / "audio_final.mp3"
    voice_path.write_bytes(b"voice")

    with patch(
        "app.modules.audio.audio_mixer.ProjectManager",
        side_effect=AssertionError("No debe resolver el proyecto desde entorno."),
    ):
        result = AudioMixer().build(
            voice_path=voice_path,
            output_path=output_path,
            project=object(),
        )

    assert result == output_path
    assert output_path.read_bytes() == b"voice"
