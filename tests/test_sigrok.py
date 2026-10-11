from types import SimpleNamespace

from dl16_mcp import sigrok


def test_missing_sigrok_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr(sigrok.shutil, "which", lambda _: None)
    assert sigrok.decode_vcd(tmp_path / 'x', 'uart', {'rx': 8})['error_code'] == 'SIGROK_MISSING'


def test_invalid_decoder_no_process(monkeypatch, tmp_path):
    monkeypatch.setattr(sigrok.shutil, 'which', lambda _: (_ for _ in ()).throw(AssertionError()))
    assert not sigrok.decode_vcd(tmp_path / 'x', 'uart:evil', {'rx': 8})['success']
    assert not sigrok.decode_vcd(tmp_path / 'x', 'uart', {'rx': 8}, {'baudrate': '1:evil'})['success']


def test_bounded_output_and_no_shell(monkeypatch, tmp_path):
    source = tmp_path / 'x.vcd'; source.write_text('$enddefinitions $end')
    monkeypatch.setattr(sigrok.shutil, 'which', lambda _: 'sigrok-cli')
    def execute(args, **kwargs):
        assert args[-1] == 'uart:rx=8:baudrate=115200'
        assert 'shell' not in kwargs
        kwargs['stdout'].write(b'a' * 70000)
        kwargs['stderr'].write(b'warning')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(sigrok.subprocess, 'run', execute)
    result = sigrok.decode_vcd(source, 'uart', {'rx': 8}, {'baudrate': '115200'})
    assert result['success'] and result['truncated'] and len(result['output']) == 65536


def test_timeout_is_failure(monkeypatch, tmp_path):
    source = tmp_path / 'x.vcd'; source.write_text('vcd')
    monkeypatch.setattr(sigrok.shutil, 'which', lambda _: 'sigrok-cli')
    def execute(*args, **kwargs):
        raise sigrok.subprocess.TimeoutExpired('sigrok', 1)
    monkeypatch.setattr(sigrok.subprocess, 'run', execute)
    assert sigrok.decode_vcd(source, 'uart', {'rx': 8})['error_code'] == 'SIGROK_EXEC_FAILED'
