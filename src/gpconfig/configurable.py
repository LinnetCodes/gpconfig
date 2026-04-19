"""GPConfigurable base class for configurable objects."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gpconfig.config import GPConfig


class GPConfigurable:
    """
    Base class for objects that are configured by GPConfig subclasses.

    Subclasses must accept a single config parameter in __init__:
        def __init__(self, config: MyConfigSubclass) -> None:
            super().__init__(config)
            # Initialize from config values
    """

    def __init__(self, config: "GPConfig") -> None:
        """
        Initialize the configurable object from its config.

        Args:
            config: A GPConfig subclass instance containing this object's settings
        """
        self._config = config

    @property
    def config(self) -> "GPConfig":
        """Access the configuration object."""
        return self._config
