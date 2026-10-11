"""Experimental archive writer for the documented offline reader subset.

GUI compatibility is not certified. Source provenance is retained, never promoted.
"""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path

from .artifacts import Waveform


def write_atkdl(waveforms: list[Waveform], destination: Path) -> dict:
    if (not waveforms or len({w.channel for w in waveforms}) != len(waveforms)
            or any(w.samples <= 0 or len(w.raw) * 8 < w.samples for w in waveforms)
            or len({(w.sample_rate_hz, w.samples) for w in waveforms}) != 1):
        raise ValueError('channels must have matching positive sample rate and depth')
    if destination.suffix.lower() != '.atkdl':
        raise ValueError('destination must be .atkdl')
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    first = waveforms[0]
    settings = {'setHz': first.sample_rate_hz, 'setTime': first.samples * 1000 / first.sample_rate_hz}
    metadata = {'schema': 'dl16-export-provenance/v1', 'gui_compatibility': 'UNVERIFIED',
                'channels': [{'channel': w.channel, 'samples': w.samples, 'source': w.source,
                              'integrity': w.integrity} for w in waveforms]}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('set.ini', 'settingData=' + json.dumps(settings) + '\n')
            archive.writestr('dl16-provenance.json', json.dumps(metadata))
            for waveform in waveforms:
                data = bytearray(waveform.raw[:(waveform.samples + 7) // 8])
                if waveform.samples % 8:
                    data[-1] &= (1 << (waveform.samples % 8)) - 1
                archive.writestr(f'{waveform.channel}/{waveform.channel}-0.bin', data)
        # Exclusive publication protects a concurrently created destination.
        with destination.open('xb') as output, temporary.open('rb') as source:
            import shutil
            shutil.copyfileobj(source, output)
            output.flush(); os.fsync(output.fileno())
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {'success': True, 'path': str(destination.resolve()), 'gui_compatibility': 'UNVERIFIED',
            'format_scope': 'offline-reader subset', 'source_provenance_preserved': True}
