# Installation

## Core and reproducible build

Use Python 3.11+ on POSIX; 3.12 is the tested baseline. In a new checkout create a private environment, then `python -m pip install .`. `video-analyzer` is the console command. Source-only operation is also supported: `python cli.py --help` or `./video-analyzer --help` (the shell wrapper prefers local `.venv`, otherwise `PYTHON` / `python3`). Do not replace your production checkout or environment.

For an offline install, obtain reviewed wheels for setuptools (>=77) and wheel using your normal trusted distribution channel. With these already installed in the build environment:

```sh
python -m pip wheel --no-deps --no-build-isolation --no-index . --wheel-dir /tmp/research-wheels
python -m pip install --no-deps --no-index /tmp/research-wheels/research_video_analyzer-1.4.0-py3-none-any.whl
```

No model or network call occurs from core imports, help, doctor, session creation or the synthetic example. `doctor` lists optional capabilities as unavailable without failing the core check. It does not validate provider quota or prove media playback.

## Optional dependencies

| Extra | Purpose | Additional requirements |
|---|---|---|
| `video` | yt-dlp metadata/subtitles/media; FFmpeg fallback | Network/platform access; Node on PATH for relevant YouTube challenges |
| `audio` | Local VAD/ASR, media/audio metrics | Existing model files; native wheels, FFmpeg; optional whisper.cpp binary |
| `documents` | Selective public HTTPS/arXiv document intake | Network, extraction/PDF libraries; not a general web crawler |
| `benchmark` | Traditional/Simplified Chinese normalization | Explicit local input and backend models |

Extras describe direct requirements, not a verified all-platform lock. `requirements-legacy.lock.txt` is the untouched production environment inventory; it is not the public default installation contract and may not resolve on other Python versions/platforms. `requirements-document-intake.lock.txt` is a historical optional hash lock; availability on a fresh index is unverified. No dependency upgrades were installed during this preparation.

## Private runtime configuration

Copy `runtime.example.json` to a private `runtime.json`. Set existing model paths and the local whisper-cli path, record actual backend versions, then export `RESEARCH_RUNTIME=/absolute/path/to/runtime.json`. Relative paths resolve against that configuration file. Missing files produce explicit errors; no implicit model download. Audio analysis remains opt-in via `audio-analyze --enable`; sound-event analysis stays unqualified/disabled.

Global `--data` / `--cache` override the corresponding `RESEARCH_*` environment variables. Defaults are separate from production and writable outside site-packages. `RESEARCH_RUNTIME` is the only runtime-config override; the installed package's example supplies disabled defaults. `.env` is never automatically sourced.

## Preserve existing installations

Use a new venv and new state directories. This candidate does not migrate sessions or rewrite artifact paths. Existing sessions can contain absolute pinned-artifact paths; copying them is not a verified migration. Do not point experimental tools at the live production Store.
