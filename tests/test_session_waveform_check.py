import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from session_waveform_check import check_pwm_bits


def test_known_pwm_and_static_fail(tmp_path):
    p = tmp_path / "signal.bits"
    bits = ((np.arange(200000) % 20000) < 10000).astype(np.uint8)
    p.write_bytes(np.packbits(bits, bitorder="little").tobytes())
    result = check_pwm_bits(p, 200000, 20000000, 1000)
    assert result["valid"] and result["frequency_hz"] == 1000
    p.write_bytes(bytes(25000))
    assert not check_pwm_bits(p, 200000, 20000000, 1000)["valid"]


def test_short_and_wrong_frequency_fail(tmp_path):
    p = tmp_path / "signal.bits"
    p.write_bytes(b"\x00")
    assert not check_pwm_bits(p, 200000, 20000000, 1000)["valid"]
    bits = ((np.arange(200000) % 10000) < 5000).astype(np.uint8)
    p.write_bytes(np.packbits(bits, bitorder="little").tobytes())
    assert not check_pwm_bits(p, 200000, 20000000, 1000)["valid"]
