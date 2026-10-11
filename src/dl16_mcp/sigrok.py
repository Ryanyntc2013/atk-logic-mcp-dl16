"""Optional bounded sigrok-cli host; never invokes a shell or USB acquisition."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def decode_vcd(path: Path, decoder: str, channels: dict[str, int],
               options: dict[str, str] | None = None, timeout_s: float = 30) -> dict[str, Any]:
    if (not NAME.fullmatch(decoder) or not channels or not 1 <= timeout_s <= 120
            or any(not NAME.fullmatch(k) or type(v) is not int or not 0 <= v <= 15
                   for k, v in channels.items())
            or any(not NAME.fullmatch(k) or not isinstance(v, str) or not v
                   or len(v) > 128 or any(c in v for c in ':=\r\n')
                   for k, v in (options or {}).items())):
        return {"success": False, "error_code": "INVALID_SIGROK_CONFIG"}
    exe = shutil.which("sigrok-cli")
    if exe is None:
        return {"success": False, "error_code": "SIGROK_MISSING",
                "message": "Install sigrok-cli explicitly; internal UART/I2C/SPI remain available"}
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        return {"success": False, "error_code": "SIGROK_INPUT_INVALID"}
    spec = decoder + ''.join(f':{k}={v}' for k, v in sorted(channels.items()))
    spec += ''.join(f':{k}={v}' for k, v in sorted((options or {}).items()))
    import tempfile
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            proc = subprocess.run([exe, '-i', str(path.resolve()), '-I', 'vcd', '-P', spec],
                                  stdout=stdout, stderr=stderr, timeout=timeout_s, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"success": False, "error_code": "SIGROK_EXEC_FAILED", "message": str(exc)[:1024]}
        stdout.seek(0); stderr.seek(0)
        output = stdout.read(65537); errors = stderr.read(4096)
        return {"success": proc.returncode == 0, "decoder": decoder,
                "output": output[:65536].decode('utf-8', errors='replace'),
                "truncated": len(output) > 65536, "stderr": errors.decode('utf-8', errors='replace'),
                "returncode": proc.returncode, "evidence_source": "OFFLINE_EXTERNAL_DECODER"}
