from pathlib import Path

import dl16_mcp
import protocol_reference


def test_tests_import_this_repository():
    root = Path(__file__).resolve().parents[1]
    assert Path(dl16_mcp.__file__).resolve() == root / "src" / "dl16_mcp" / "__init__.py"
    assert Path(protocol_reference.__file__).resolve() == root / "tests" / "protocol_reference.py"
