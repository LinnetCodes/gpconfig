"""Tests for custom exceptions."""

from gpconfig.exceptions import (
    GPConfigError,
    ConfigFolderError,
    ConfigNotFoundError,
    ConfigReadonlyError,
    RegistrationError,
    ConfigValidationError,
)


class TestExceptionHierarchy:
    """Test that all exceptions inherit from GPConfigError."""

    def test_config_folder_error_is_gpconfig_error(self):
        assert issubclass(ConfigFolderError, GPConfigError)

    def test_config_not_found_error_is_gpconfig_error(self):
        assert issubclass(ConfigNotFoundError, GPConfigError)

    def test_config_readonly_error_is_gpconfig_error(self):
        assert issubclass(ConfigReadonlyError, GPConfigError)

    def test_registration_error_is_gpconfig_error(self):
        assert issubclass(RegistrationError, GPConfigError)

    def test_config_validation_error_is_gpconfig_error(self):
        assert issubclass(ConfigValidationError, GPConfigError)


class TestConfigNotFoundError:
    """Test ConfigNotFoundError specific behavior."""

    def test_stores_path_attribute(self):
        error = ConfigNotFoundError("some.path")
        assert error.path == "some.path"

    def test_default_message_includes_path(self):
        error = ConfigNotFoundError("some.path")
        assert "some.path" in str(error)
        assert "Config not found" in str(error)

    def test_custom_message_overrides_default(self):
        error = ConfigNotFoundError("some.path", "Custom message")
        assert str(error) == "Custom message"


class TestConfigValidationError:
    """Test ConfigValidationError specific behavior."""

    def test_stores_path_attribute(self):
        original = ValueError("bad value")
        error = ConfigValidationError("some.yaml", original)
        assert error.path == "some.yaml"

    def test_stores_original_error(self):
        original = ValueError("bad value")
        error = ConfigValidationError("some.yaml", original)
        assert error.original_error is original

    def test_message_includes_path_and_original(self):
        original = ValueError("bad value")
        error = ConfigValidationError("some.yaml", original)
        msg = str(error)
        assert "some.yaml" in msg
        assert "bad value" in msg
