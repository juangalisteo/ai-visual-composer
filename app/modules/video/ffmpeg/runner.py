import subprocess


class Runner:

    def run(
        self,
        command
    ):
        subprocess.run(
            command,
            check=True
        )