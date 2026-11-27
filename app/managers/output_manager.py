from pathlib import Path
import shutil

from app.managers.project_manager import ProjectManager
from app.shared.operational_error import create_operational_error
from app.shared.progress_logger import ProgressLogger


OUTPUT_ROOT = Path("output")


def project_folder_in_output(folder, output_root=OUTPUT_ROOT):
    """True when ``folder`` is a folder directly inside output/.

    Names such as «.» or «..» would point at output/ itself or outside it:
    they are never a project folder, so they are never overwritten.
    """
    return Path(folder).resolve().parent == Path(output_root).resolve()


class OutputManager:
    """Removes the folder of one project before it is written again.

    Emptying the whole output/ folder is not part of the program: the user
    deletes old projects by hand.
    """

    def __init__(
        self,
        output_path=OUTPUT_ROOT
    ):
        self.output_path = Path(
            output_path
        )

    def remove_project(
        self,
        project_name
    ):
        project = ProjectManager(
            project_name=project_name
        )
        folder = (
            self.output_path
            / project.project_name
        )
        if not project_folder_in_output(folder, self.output_path):
            raise create_operational_error(
                family="VALIDATION",
                user_message=(
                    f"«{project.project_name}» no es una carpeta de "
                    "proyecto dentro de output/."
                ),
                recommended_action="Elige otro nombre de proyecto.",
                operation="Sobrescribir el proyecto",
                resource=folder.as_posix(),
            )
        if not folder.exists():
            return

        try:
            if folder.is_dir():
                shutil.rmtree(
                    folder
                )
            else:
                folder.unlink()
        except PermissionError as error:
            if getattr(error, "winerror", None) != 32:
                raise
            raise create_operational_error(
                family="FILESYSTEM",
                user_message=(
                    f"No se puede sobrescribir el proyecto «{project.project_name}» "
                    "porque uno de sus archivos está siendo utilizado por otro "
                    "programa."
                ),
                recommended_action="Cierra el archivo y vuelve a intentarlo.",
                operation="Sobrescribir el proyecto",
                resource=error.filename,
            ) from error

        ProgressLogger.info(
            f"Proyecto «{project.project_name}» borrado para sobrescribirlo."
        )
