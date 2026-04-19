# tests/test_exports.py
"""Tests for package public API exports."""


class TestPublicAPI:
    """Test that all public classes are exported from the package."""

    def test_export_gpconfig(self):
        from gpconfig import GPConfig

        assert GPConfig is not None

    def test_export_gpconfigurable(self):
        from gpconfig import GPConfigurable

        assert GPConfigurable is not None

    def test_export_gpconfigmanager(self):
        from gpconfig import GPConfigManager

        assert GPConfigManager is not None

    def test_export_exceptions(self):
        from gpconfig import (
            GPConfigError,
            ConfigFolderError,
            ConfigNotFoundError,
            ConfigReadonlyError,
            RegistrationError,
            ConfigValidationError,
        )

        assert GPConfigError is not None
        assert ConfigFolderError is not None
        assert ConfigNotFoundError is not None
        assert ConfigReadonlyError is not None
        assert RegistrationError is not None
        assert ConfigValidationError is not None

    def test_all_exports_in_dunder_all(self):
        import gpconfig

        expected = {
            "GPConfig",
            "GPConfigurable",
            "GPConfigManager",
            "GPConfigError",
            "ConfigFolderError",
            "ConfigNotFoundError",
            "ConfigReadonlyError",
            "RegistrationError",
            "ConfigValidationError",
        }
        assert expected.issubset(set(gpconfig.__all__))
