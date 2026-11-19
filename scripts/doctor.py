#!/usr/bin/env python3
"""Offline capability diagnostics: no installation, model call or download."""
import importlib.util
import json
import shutil
from pathlib import Path
import sys
from va import load_runtime

cfg = load_runtime()
checks = [dict(component='Python >=3.11 POSIX', ok=sys.version_info >= (3,11) and sys.platform != 'win32')]
optional = [dict(component=name, available=importlib.util.find_spec(name) is not None)
            for name in ('yt_dlp','imageio_ffmpeg','faster_whisper','trafilatura','pypdf')]
optional += [dict(component=name, available=bool(shutil.which(name))) for name in ('ffmpeg','node','agy','sandbox-exec')]
optional += [dict(component='whisper.cpp', available=Path(cfg['whisper_cli']).is_file())]
optional += [dict(component=f'{backend}/{name}', available=Path(path).exists())
             for backend, models in cfg['models'].items() for name,path in models.items()]
print(json.dumps(dict(ok=all(c['ok'] for c in checks),checks=checks,optional=optional),indent=2))
sys.exit(0 if all(c['ok'] for c in checks) else 2)
