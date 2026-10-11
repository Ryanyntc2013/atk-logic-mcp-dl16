import pytest

from dl16_mcp.artifacts import Waveform, load_atkdl
from dl16_mcp.atkdl_export import write_atkdl


def test_reader_roundtrip_not_gui_certificate(tmp_path):
    waveform = Waveform(8, b'\xff\xff', 9, 1000000, 'COMPLETE', 'SYNTHETIC', {})
    target = tmp_path / 'x.atkdl'
    result = write_atkdl([waveform], target)
    assert result['gui_compatibility'] == 'UNVERIFIED'
    loaded = load_atkdl(target, 8)
    assert loaded.samples == 9 and loaded.raw == b'\xff\x01'
    assert loaded.source == 'SAVED_ATKDL'
    with pytest.raises(FileExistsError):
        write_atkdl([waveform], target)


def test_mismatched_channels_rejected(tmp_path):
    a = Waveform(8, b'\xff', 8, 1000000, 'COMPLETE', 'SYNTHETIC', {})
    b = Waveform(14, b'\xff', 8, 2000000, 'COMPLETE', 'SYNTHETIC', {})
    with pytest.raises(ValueError):
        write_atkdl([a, b], tmp_path / 'bad.atkdl')
