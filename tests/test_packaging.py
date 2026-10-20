# tests/test_packaging.py
"""Tests for packaging metadata (PEP 561 marker, etc.)."""


class TestPyTypedMarker:
    """The package ships a py.typed marker so type checkers consume its inline types."""

    def test_py_typed_marker_ships_with_package(self):
        from pathlib import Path

        import gpconfig

        package_dir = Path(gpconfig.__file__).resolve().parent
        assert (package_dir / "py.typed").is_file()
