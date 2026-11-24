"""Chatterbox Multilingual worker, run with the voice environment's Python.

``ChatterboxBackend`` launches it as a separate process (protocol in
``app/modules/audio/external_tts_process.py``):

    <env python> -I -X utf8 chatterbox_worker.py <request.json>

It loads the model from the declared checkpoint folder, writes one 16-bit
mono WAV per segment and the result document, and exits, so the GPU memory
is released. Only the standard library is imported at module level: the
project's tests import this file without torch. It must run on Python 3.11.
"""

import json
from pathlib import Path
import random
import sys
import time
import traceback


PROTOCOL_VERSION = 1
PROGRESS_PREFIX = "AIVC_PROGRESS"


class WorkerError(Exception):
    """Failure with a result kind and a Spanish message for the user."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind
        self.message = message


def main(argv):
    if len(argv) != 2:
        print("Uso: chatterbox_worker.py <request.json>", file=sys.stderr)
        return 2
    request = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    result_path = Path(request["result"])
    try:
        if request.get("protocol") != PROTOCOL_VERSION:
            raise WorkerError(
                "configuration",
                f"el script de la voz espera el protocolo {PROTOCOL_VERSION} y "
                f"recibió {request.get('protocol')!r}.",
            )
        sample_rate, timings = synthesize(request)
    except WorkerError as error:
        write_result(
            result_path,
            {"status": "error", "kind": error.kind, "message": error.message},
        )
        return 1
    except Exception as error:
        traceback.print_exc()
        write_result(
            result_path,
            {
                "status": "error",
                "kind": "synthesis",
                "message": f"{type(error).__name__}: {error}",
            },
        )
        return 1
    write_result(
        result_path,
        {"status": "ok", "sample_rate": sample_rate, **timings},
    )
    return 0


def synthesize(request):
    """Read every segment with one model load.

    Returns the sample rate and the load and generation times, in seconds.
    """
    import numpy as np
    import soundfile as sf
    import torch

    device = request["device"]
    if device == "cuda" and not torch.cuda.is_available():
        raise WorkerError(
            "resource_unavailable",
            "la GPU (CUDA) no está disponible en el entorno de la voz.",
        )
    seed = request.get("seed")
    if seed is not None:
        fix_seed(seed, np, torch)

    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    start = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_local(request["checkpoint_dir"], device)
    loaded = time.perf_counter()
    segments = request["segments"]
    for index, segment in enumerate(segments, start=1):
        wav = model.generate(
            segment["text"],
            language_id=request["language_id"],
            **request["synthesis"],
        )
        audio = np.asarray(wav.squeeze(0).cpu().numpy(), dtype=np.float32)
        sf.write(segment["output"], audio.reshape(-1), model.sr, subtype="PCM_16")
        print(f"{PROGRESS_PREFIX} {index} {len(segments)}", flush=True)
    timings = {
        "load_seconds": round(loaded - start, 2),
        "generation_seconds": round(time.perf_counter() - loaded, 2),
    }
    return int(model.sr), timings


def fix_seed(seed, np, torch):
    """Fix every random source Chatterbox samples from, before loading."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def write_result(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
