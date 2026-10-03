#!/usr/bin/env python3
"""
dtline runner: generates images via the Draw Things gRPC CLI.

Calls the `dtline` CLI (https://github.com/Alexthestampede/dtline) with
--json and returns parsed output. Settings from config['dtline'] map to
CLI flags (model, preset, size, steps, seed, output_dir).
"""
import json
import shutil
import subprocess
from typing import Dict, Any, List, Optional


class DtlineError(RuntimeError):
    """dtline invocation failed."""


def dtline_available() -> bool:
    return shutil.which('dtline') is not None


def run_dtline(prompt: str, settings: Dict[str, Any],
               timeout: int = 600) -> Dict[str, Any]:
    """Generate an image; returns parsed --json output.

    Raises DtlineError on failure.

    settings keys (all optional): model, preset, size, steps, seed,
        output_dir, neg_preset
    """
    if not dtline_available():
        raise DtlineError(
            "dtline not found in PATH. Install it from "
            "https://github.com/Alexthestampede/dtline")

    cmd = ['dtline', 'generate', prompt, '--json']
    for key, flag in (('model', '--model'), ('preset', '--preset'),
                      ('steps', '--steps'),
                      ('seed', '--seed'), ('neg_preset', '--negative-preset')):
        val = settings.get(key)
        if val not in (None, ''):
            if key == 'steps':
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    continue
            cmd += [flag, str(val)]
    # size may be "1:1 1024x1024" (dtline config notation) -> aspect-ratio flag
    size = settings.get('size')
    if size:
        size = str(size).strip()
        args = size.split()
        if args:
            first = args[0]
            if ':' in first:          # aspect ratio like "1:1"
                cmd += ['--aspect-ratio', first]
                # optional "WxH" part -> explicit --width/--height
                if len(args) > 1 and 'x' in args[1]:
                    w_str, h_str = args[1].lower().split('x', 1)
                    if w_str.isdigit() and h_str.isdigit():
                        cmd += ['--width', w_str, '--height', h_str]
            elif 'x' in first.lower():
                w_str, h_str = first.lower().split('x', 1)
                if w_str.isdigit() and h_str.isdigit():
                    cmd += ['--width', w_str, '--height', h_str]
            else:
                cmd += ['--aspect-ratio', first]
    out_dir = settings.get('output_dir')
    if out_dir:
        import os
        os.makedirs(out_dir, exist_ok=True)
        cmd += ['--output-dir', str(out_dir)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise DtlineError(f"dtline timed out after {timeout}s")
    except Exception as e:
        raise DtlineError(str(e))

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or '').strip()[-500:]
        raise DtlineError(f"dtline failed: {detail or 'unknown error'}")

    try:
        data = json.loads(proc.stdout)
    except ValueError:
        raise DtlineError(f"dtline returned non-JSON: {proc.stdout[:200]}")

    if not data.get('success'):
        err = (data.get('error') or {}).get('message', 'unknown error')
        raise DtlineError(f"dtline error: {err}")

    # normalize images list entries to have 'path'
    images: List[Dict] = data.get('images') or []
    return data


def list_models() -> List[str]:
    """Human-model list from dtline (best-effort parse)."""
    if not dtline_available():
        return []
    try:
        proc = subprocess.run(['dtline', 'list-models', '--json'],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            models = data if isinstance(data, list) else data.get('models', [])
            return [m.get('name') or m.get('model') or str(m) if isinstance(m, dict) else str(m)
                    for m in models]
    except Exception:
        pass
    return []