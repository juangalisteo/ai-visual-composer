"""Primitive de consola que preserva la política actual de selección."""

from app.shared.progress_logger import ProgressLogger


class Terminal:
    """Encapsula entrada y salida sin apropiarse de la cancelación."""

    def __init__(self, reader=None, writer=None):
        self._reader = reader
        self._writer = writer

    def write(self, message):
        if self._writer is not None:
            self._writer(message)
            return
        ProgressLogger.info(message)

    def read(self, prompt):
        return (self._reader or input)(prompt)

    def select_from_list(self, items, on_cancel):
        while True:
            option = self.read("\n> ").strip()

            if option == "0":
                on_cancel()

            if option.isdigit():
                index = int(option)
                if 1 <= index <= len(items):
                    return items[index - 1]

            self.write("\nOpción no válida.")
