"""Toolchain smoke test — confirms the package imports and version is exposed."""

import gate


def test_package_exposes_version() -> None:
    assert gate.__version__ == "0.1.0"
