"""Actual production dispatcher contracts with a USB-free synthetic owner."""
import json
import subprocess
import time
from pathlib import Path

import pytest

from dl16_mcp import backend
from dl16_mcp.config import CaptureRequest
from dl16_mcp.session import NativeSession, SessionFailure

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'tests' / 'native' / 'build' / 'Release' / 'dl16-async-buffer-test.exe'
NATIVE = ROOT / 'external' / 'ATK-Logic-Mcp' / 'build' / 'Release' / 'atk-dl16.exe'


def start_request(**kwargs):
    return {'command': 'capture_start', 'channels': [8, 14], 'sample_rate_hz': 20_000_000,
            'duration_ms': 20, 'threshold_voltage': 1.6, **kwargs}


@pytest.mark.skipif(not HARNESS.exists(), reason='native USB-free dispatcher harness not built')
def test_actual_native_cancel_error_serialization():
    reply = subprocess.run([str(HARNESS), 'cancel-result'], capture_output=True, text=True, check=True)
    result = json.loads(reply.stdout)
    assert result['success'] is False
    assert result['data_integrity'] == 'INCOMPLETE'
    assert result['error_code'] == 'INCOMPLETE_CAPTURE'
    assert 'cancelled' in result['message']


@pytest.mark.skipif(not HARNESS.exists(), reason='native USB-free dispatcher harness not built')
def test_actual_dispatcher_cancel_busy_poll_close():
    session = NativeSession(HARNESS)
    try:
        result = session.request(start_request(), timeout_s=2)
        operation = result['operation_id']
        with pytest.raises(SessionFailure, match='active BUFFER'):
            session.request({'command': 'status'}, timeout_s=2)
        with pytest.raises(SessionFailure, match='active BUFFER'):
            session.request({'command': 'close'}, timeout_s=2)
        with pytest.raises(SessionFailure, match='does not match'):
            session.request({'command': 'capture_cancel', 'operation_id': 'wrong'}, timeout_s=2)
        begin = time.monotonic()
        session.request({'command': 'capture_cancel', 'operation_id': operation}, timeout_s=2)
        while True:
            result = session.request({'command': 'capture_poll', 'operation_id': operation}, timeout_s=2)
            if result['state'] == 'finished':
                break
            assert time.monotonic() - begin < 1
        assert result['response']['result']['cancel_observed']
        assert result['response']['result']['data_integrity'] == 'INCOMPLETE'
        assert time.monotonic() - begin < 1
    finally:
        session.close()
    assert session.pid is None


@pytest.mark.skipif(not HARNESS.exists(), reason='native USB-free dispatcher harness not built')
def test_actual_dispatcher_eof_cancels_and_joins():
    proc = subprocess.Popen([str(HARNESS)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    proc.stdin.write(json.dumps({'request_id': 'a', **start_request()}) + '\n')
    proc.stdin.flush()
    assert json.loads(proc.stdout.readline())['ok']
    begin = time.monotonic()
    proc.stdin.close()
    assert proc.wait(timeout=2) == 0
    assert time.monotonic() - begin < 1
    proc.stdout.close()


@pytest.mark.skipif(not NATIVE.exists(), reason='patched native not built')
@pytest.mark.parametrize('changes', [{'channels': [0, 1, 2]}, {'duration_ms': 30001},
                                   {'sample_rate_hz': 40_000_000}, {'mode': 'stream'},
                                   {'trigger': 'ch8:rising'}, {'rle': True}])
def test_actual_worker_invalid_async_never_opens_usb(changes):
    session = NativeSession(NATIVE)
    try:
        with pytest.raises(SessionFailure) as error:
            session.request(start_request(**changes), timeout_s=2)
        assert error.value.code == 'INVALID_CAPTURE'
    finally:
        session.close()


@pytest.mark.parametrize('capture_request', [CaptureRequest((0, 1, 2)),
                                    CaptureRequest((0,), 40_000_000),
                                    CaptureRequest((0,), duration_ms=30001),
                                    CaptureRequest((0,), rle=True)])
def test_host_rejects_before_launch(monkeypatch, capture_request):
    monkeypatch.setattr(backend, 'find_native_cli', lambda: pytest.fail('must not launch'))
    assert backend.buffer_start(capture_request)['error_code'] == 'INVALID_CAPTURE'


def test_poll_never_creates_owner(monkeypatch):
    monkeypatch.setattr(backend, '_SESSION', None)
    monkeypatch.setattr(backend, '_get_session', lambda _: pytest.fail('must not create owner'))
    assert backend.buffer_control('lost')['error_code'] == 'NO_ACTIVE_SESSION'


@pytest.mark.skipif(not HARNESS.exists(), reason='native dispatcher harness not built')
def test_actual_partial_artifact_fail_closed(tmp_path, monkeypatch):
    from dl16_mcp.artifacts import load_capture

    monkeypatch.setenv('DL16_DATA_DIR', str(tmp_path))
    folder = tmp_path / 'captures'
    result = subprocess.run([str(HARNESS), 'artifact', str(folder)], check=False)
    assert result.returncode == 0
    meta = json.loads((folder / 'partial' / 'meta.json').read_text())
    assert meta['partial_uncropped'] is True
    assert meta['data_integrity'] == 'INCOMPLETE'
    assert meta['edges_omitted'] is True
    assert (folder / 'partial' / 'ch08.bits').read_bytes() == bytes([0x55, 0xaa])
    with pytest.raises(ValueError, match='not analysis-ready'):
        load_capture('partial', 8)
    failed = subprocess.run([str(HARNESS), 'artifact', str(folder / 'partial' / 'meta.json')], check=False)
    assert failed.returncode == 2


@pytest.mark.skipif(not HARNESS.exists(), reason='native dispatcher harness not built')
def test_close_active_operation_cooperatively():
    session = NativeSession(HARNESS)
    session.request(start_request(), timeout_s=2)
    started = time.monotonic()
    session.close()
    assert time.monotonic() - started < 1
    assert session.pid is None
