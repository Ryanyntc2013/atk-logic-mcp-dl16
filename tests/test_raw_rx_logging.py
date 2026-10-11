import json
from pathlib import Path
import subprocess

import pytest

from dl16_mcp import backend
from dl16_mcp.config import CaptureRequest
from dl16_mcp.session import NativeSession, SessionFailure

ROOT = Path(__file__).resolve().parents[1]


def test_actual_native_writer(tmp_path):
    exe = ROOT / 'tests' / 'native' / 'build' / 'Release' / 'dl16-raw-rx-logging-test.exe'
    if not exe.is_file():
        pytest.skip('native writer harness not built')
    result = subprocess.run([str(exe), str(tmp_path / 'writer')], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS:' in result.stdout
    assert (tmp_path / 'writer-cap.bin').stat().st_size == 8
    assert not (tmp_path / 'writer-over.bin').exists()


def test_actual_native_capability_no_usb():
    exe = ROOT / 'external' / 'ATK-Logic-Mcp' / 'build' / 'Release' / 'atk-dl16.exe'
    if not exe.is_file():
        pytest.skip('native CLI not built')
    result = subprocess.run([str(exe), 'capabilities'], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {'raw_rx_log': 'dl16-raw-rx/v1'}


@pytest.mark.parametrize('kind', ['relative', 'exists', 'missing', 'small', 'large', 'bool'])
def test_invalid_logging_configuration_never_launches(monkeypatch, tmp_path, kind):
    path = tmp_path / 'new.bin'
    limit = 33554432
    if kind == 'relative':
        path = Path('relative.bin')
    elif kind == 'exists':
        path.write_bytes(b'keep')
    elif kind == 'missing':
        path = tmp_path / 'missing' / 'new.bin'
    elif kind == 'small':
        limit = 7
    elif kind == 'large':
        limit += 1
    else:
        limit = True
    monkeypatch.setattr(backend, 'find_native_cli', lambda: pytest.fail('must validate before launch'))
    result = backend.capture(CaptureRequest(), raw_rx_path=path, raw_rx_max_bytes=limit)
    assert result['error_code'] == 'INVALID_CAPTURE_CONFIG'


@pytest.mark.parametrize('capability', ['', '{}', '{"raw_rx_log":"old"}'])
def test_older_binary_never_receives_logging_capture(monkeypatch, tmp_path, capability):
    calls = []
    monkeypatch.setattr(backend, 'find_native_cli', lambda: Path('fake.exe'))
    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, capability, '')
    monkeypatch.setattr(backend.subprocess, 'run', run)
    result = backend.capture(CaptureRequest(), raw_rx_path=tmp_path / 'new.bin')
    assert result['error_code'] == 'RAW_RX_UNSUPPORTED'
    assert calls == [['fake.exe', 'capabilities']]


def test_supported_logging_flags_and_failure_retained(monkeypatch, tmp_path):
    monkeypatch.setenv('DL16_BACKEND_MODE', 'oneshot')
    monkeypatch.setattr(backend, 'find_native_cli', lambda: Path('fake.exe'))
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        doc = {'raw_rx_log': 'dl16-raw-rx/v1'} if cmd[1] == 'capabilities' else {
            'success': False, 'error_code': 'ARTIFACT_WRITE_ERROR', 'data_integrity': 'INCOMPLETE',
            'raw_rx_log': {'error': 'write failed', 'truncated': False}}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(doc), '')
    monkeypatch.setattr(backend.subprocess, 'run', run)
    result = backend.capture(CaptureRequest(), raw_rx_path=tmp_path / 'new.bin', raw_rx_max_bytes=100)
    assert calls[1][-4:] == ['--raw-rx-path', str(tmp_path / 'new.bin'), '--raw-rx-max-bytes', '100']
    assert result['success'] is False
    assert result['raw_rx_log']['error'] == 'write failed'


def test_disabled_no_capability_probe(monkeypatch):
    monkeypatch.setenv('DL16_BACKEND_MODE', 'oneshot')
    monkeypatch.setattr(backend, 'find_native_cli', lambda: Path('fake.exe'))
    def run(cmd, **kwargs):
        assert cmd[1] == 'capture'
        assert '--raw-rx-path' not in cmd
        return subprocess.CompletedProcess(cmd, 1, '{"success":false}', '')
    monkeypatch.setattr(backend.subprocess, 'run', run)
    assert backend.capture(CaptureRequest())['success'] is False


def test_session_mixed_generation_logging_guard(monkeypatch):
    session = NativeSession(Path('fake.exe'))
    monkeypatch.setattr(session, '_start', lambda: None)
    session._hello = True
    session.capabilities = {'capture'}
    monkeypatch.setattr(session, '_request_locked', lambda *a, **k: pytest.fail('old worker must not receive raw flags'))
    with pytest.raises(SessionFailure, match='raw RX logging'):
        session.request({'command': 'capture', 'raw_rx_path': 'new.bin'}, timeout_s=1)


@pytest.mark.parametrize('args', [
    ['--raw-rx-path'], ['--raw-rx-max-bytes'],
    ['--raw-rx-path', 'relative.bin'], ['--raw-rx-path', ''],
    ['--raw-rx-max-bytes', '32'], ['--raw-rx-max-bytes', '-1'],
    ['--raw-rx-max-bytes', '9999999999999999999999'],
])
def test_actual_native_invalid_flags_rejected_before_usb(args):
    exe = ROOT / 'external' / 'ATK-Logic-Mcp' / 'build' / 'Release' / 'atk-dl16.exe'
    if not exe.is_file():
        pytest.skip('native CLI not built')
    result = subprocess.run([str(exe), 'capture', *args], capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert 'raw RX' in result.stderr or 'Raw RX' in result.stderr
    assert 'open device' not in result.stderr


def test_actual_native_session_hello_and_invalid_logging_no_usb(tmp_path):
    exe = ROOT / 'external' / 'ATK-Logic-Mcp' / 'build' / 'Release' / 'atk-dl16.exe'
    if not exe.is_file():
        pytest.skip('native CLI not built')
    capture = {'request_id': 'bad', 'command': 'capture', 'channels': [0],
               'sample_rate_hz': 20000000, 'duration_ms': 1, 'threshold_voltage': 1.6,
               'raw_rx_max_bytes': 32}
    lines = [json.dumps({'request_id': 'hello', 'command': 'hello', 'protocol': 1}),
             json.dumps(capture),
             json.dumps({**capture, 'request_id': 'relative', 'raw_rx_path': 'relative.bin'}),
             json.dumps({'request_id': 'close', 'command': 'close'})]
    result = subprocess.run([str(exe), 'session', '--jsonl'], input='\n'.join(lines)+'\n',
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert 'raw_rx_log_v1' in responses[0]['commands']
    assert responses[1]['error_code'] == responses[2]['error_code'] == 'INVALID_CAPTURE'
    assert responses[3]['session'] == 'closing'
