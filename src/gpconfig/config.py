"""GPConfig base class for configuration management."""

from pathlib import Path
from typing import ClassVar, Optional

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from gpconfig.exceptions import ConfigReadonlyError


class GPConfig(BaseSettings):
    """
    Base class for all configuration classes.
    Each subclass is initialized from a YAML config file.
    """

    model_config = SettingsConfigDict(
        extra="forbid",
        env_prefix="GPCFG_",
    )

    # Class-level defaults (can be overridden in subclasses)
    cfg_class_name: ClassVar[str] = "GPConfig"
    default_cfg_path: ClassVar[Optional[str]] = None

    # Instance fields (set during initialization, NOT from YAML)
    name: str = ""
    cfg_file_path: Path = Path()
    readonly: bool = False
    configured_class_name: Optional[str] = None

    def save(self) -> None:
        """Save current config state back to the YAML file.

        Raises:
            ConfigReadonlyError: If readonly is True
        """
        if self.readonly:
            raise ConfigReadonlyError(self.name)

        # Get model dump, excluding non-YAML fields
        data = self.model_dump(
            mode="python", exclude={"name", "cfg_file_path", "readonly"}
        )

        # Add cfg_class_name to the saved data
        data["cfg_class_name"] = self.cfg_class_name

        # Include configured_class_name if set
        if self.configured_class_name:
            data["configured_class_name"] = self.configured_class_name
        else:
            # Remove it from data if it exists (from model_dump)
            data.pop("configured_class_name", None)

        # Write to YAML file
        with open(self.cfg_file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
