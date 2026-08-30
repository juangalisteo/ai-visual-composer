import subprocess


class Runner:

    def run(
        self,
        command
    ):
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
