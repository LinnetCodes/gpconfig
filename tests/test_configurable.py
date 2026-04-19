"""Tests for GPConfigurable base class."""

from gpconfig.config import GPConfig
from gpconfig.configurable import GPConfigurable


class MockConfig(GPConfig):
    """Test config for GPConfigurable tests."""

    value: str
    count: int = 10


class MockConfigurable(GPConfigurable):
    """Test configurable class."""

    def __init__(self, config: MockConfig) -> None:
        super().__init__(config)
        self.value = config.value
        self.count = config.count


class TestGPConfigurableBasics:
    """Test basic GPConfigurable functionality."""

    def test_stores_config_as_protected_attribute(self):
        config = MockConfig(value="test")
        obj = MockConfigurable(config)
        assert obj._config is config

    def test_config_property_returns_config(self):
        config = MockConfig(value="test")
        obj = MockConfigurable(config)
        assert obj.config is config

    def test_subclass_can_access_config_values(self):
        config = MockConfig(value="hello", count=42)
        obj = MockConfigurable(config)
        assert obj.value == "hello"
        assert obj.count == 42


class TestGPConfigurableInheritance:
    """Test that GPConfigurable works with inheritance."""

    def test_grandchild_class(self):
        """Test a grandchild of GPConfigurable."""

        class ChildConfigurable(MockConfigurable):
            def __init__(self, config: MockConfig) -> None:
                super().__init__(config)
                self.doubled = config.count * 2

        config = MockConfig(value="test", count=5)
        obj = ChildConfigurable(config)
        assert obj.count == 5
        assert obj.doubled == 10
