"""GPConfigurable base class for configurable objects."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from gpconfig.config import GPConfig
    from gpconfig.manager import GPConfigManager


@dataclass(frozen=True, slots=True)
class GPConfigurableContext:
    """Immutable dependencies for constructing a configurable object.

    Attributes:
        manager: Manager that received the object-construction request.
        path: Canonical dotted path of the source YAML file.
    """

    manager: "GPConfigManager"
    path: str


GPConfigurableT = TypeVar("GPConfigurableT", bound="GPConfigurable")


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

    @classmethod
    def from_config(
        cls: type[GPConfigurableT],
        config: "GPConfig",
        *,
        context: GPConfigurableContext,
    ) -> GPConfigurableT:
        """Construct an object from config within a manager context.

        Args:
            config: Configuration instance for the object.
            context: Manager and canonical path for this construction request.

        Returns:
            A newly constructed instance of the configurable subclass.
        """
        return cls(config)

    @property
    def config(self) -> "GPConfig":
        """Access the configuration object."""
        return self._config
