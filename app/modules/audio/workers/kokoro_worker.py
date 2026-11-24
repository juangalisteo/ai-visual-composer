"""Kokoro worker, run with the voice environment's Python.

``KokoroBackend`` launches it as a separate process (protocol in
``app/modules/audio/external_tts_process.py``):

    <env python> -I -X utf8 kokoro_worker.py <request.json>

It loads the model and the voice from the declared files, writes one 16-bit
mono WAV per segment and the result document, and exits, so the GPU memory
is released. Only the standard library is imported at module level: the
project's tests import this file without torch. It must run on Python 3.12.
The worker runs isolated (``-I``), so it cannot import a sibling module: the
protocol helpers are its own.
"""

import json
from pathlib import Path
import random
import sys
import time
import traceback


PROTOCOL_VERSION = 1
PROGRESS_PREFIX = "AIVC_PROGRESS"
# Kokoro always writes 24 kHz audio (fixed inside its code, not a setting).
SAMPLE_RATE_HZ = 24_000
# Kokoro reads at most 510 phonemes per call and silently cuts the rest.
MAX_PHONEMES = 510


class WorkerError(Exception):
    """Failure with a result kind and a Spanish message for the user."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind
        self.message = message


def main(argv):
    if len(argv) != 2:
        print("Uso: kokoro_worker.py <request.json>", file=sys.stderr)
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

    from kokoro import KModel, KPipeline
    from kokoro.pipeline import ALIASES, LANG_CODES

    lang_code = resolve_lang_code(request["lang_code"], ALIASES, LANG_CODES)
    start = time.perf_counter()
    model = KModel(
        repo_id=request["repo_id"],
        config=request["config_path"],
        model=request["weights_path"],
    ).to(device).eval()
    pipeline = KPipeline(lang_code=lang_code, repo_id=request["repo_id"], model=model)
    loaded = time.perf_counter()
    segments = request["segments"]
    for index, segment in enumerate(segments, start=1):
        pieces = []
        for result in pipeline(
            segment["text"],
            voice=request["voice_path"],
            speed=request["speed"],
        ):
            check_phonemes(result.phonemes, index)
            if result.audio is not None:
                pieces.append(np.asarray(result.audio, dtype=np.float32).reshape(-1))
        if not pieces:
            raise WorkerError(
                "synthesis",
                f"Kokoro no generó audio para la parte {index} del texto.",
            )
        sf.write(
            segment["output"],
            np.concatenate(pieces),
            SAMPLE_RATE_HZ,
            subtype="PCM_16",
        )
        print(f"{PROGRESS_PREFIX} {index} {len(segments)}", flush=True)
    timings = {
        "load_seconds": round(loaded - start, 2),
        "generation_seconds": round(time.perf_counter() - loaded, 2),
    }
    return SAMPLE_RATE_HZ, timings


def resolve_lang_code(value, aliases, lang_codes):
    """Kokoro's language code, accepting its aliases (``es`` → ``e``)."""
    code = str(value).strip().lower()
    code = aliases.get(code, code)
    if code not in lang_codes:
        raise WorkerError(
            "configuration",
            f"backend_options.voice.lang_code {value!r} no es un idioma de "
            f"Kokoro. Valores válidos: {', '.join(sorted(lang_codes))}.",
        )
    return code


def check_phonemes(phonemes, index):
    """Stop instead of letting Kokoro cut a part that is too long."""
    if len(phonemes or "") >= MAX_PHONEMES:
        raise WorkerError(
            "synthesis",
            f"la parte {index} del texto es demasiado larga para Kokoro (más de "
            f"{MAX_PHONEMES - 1} fonemas) y se cortaría. Baja "
            "backend_options.segmentation.max_characters o parte esa frase.",
        )


def fix_seed(seed, np, torch):
    """Fix every random source Kokoro samples from, before loading."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def write_result(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
