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

    def __init_subclass__(cls, **kwargs):
        """Validate subclass ClassVars at class-definition time (fail-early).

        Ensures default_cfg_path (if overridden by a subclass) conforms to the
        save() folder-path contract: it must be a string (or None) containing no
        '.' — the same rule enforced at runtime by
        GPConfigManager._resolve_save_folder. Validating at class definition
        catches typos (e.g. 'cache/redis.yaml', 'llm.openai') at import time
        rather than on the first save() call.

        Only the subclass's OWN override is inspected, not the inherited None
        default, so subclasses that don't override default_cfg_path are
        unaffected. The runtime check in _resolve_save_folder remains as
        defence-in-depth against dynamic mutation (e.g.
        ``cls.default_cfg_path = "bad"``) after class definition, which bypasses
        this hook.

        Raises:
            TypeError: If default_cfg_path is set to a non-string, non-None
                value.
            ValueError: If default_cfg_path contains '.' (rejects cfg_path
                style, '.yaml' suffix, '..' traversal, leading/trailing dots).
        """
        super().__init_subclass__(**kwargs)
        # cls.__dict__ holds only attributes defined directly on this subclass,
        # so the inherited None default from GPConfig never triggers validation.
        default_cfg_path = cls.__dict__.get("default_cfg_path")
        if default_cfg_path is not None:
            if not isinstance(default_cfg_path, str):
                raise TypeError(
                    f"{cls.__name__}.default_cfg_path must be a string or None, "
                    f"got {type(default_cfg_path).__name__}"
                )
            if "." in default_cfg_path:
                raise ValueError(
                    f"{cls.__name__}.default_cfg_path must not contain '.'; "
                    f"it is a folder path (file-system style, '/' or '\\' separated), "
                    f"not a cfg_path or file name. Got: {default_cfg_path!r}"
                )

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

        # All metadata fields are excluded from the dump uniformly;
        # fields that need to appear in the YAML are added back explicitly below.
        data = self.model_dump(
            mode="python",
            exclude={
                "name",
                "cfg_file_path",
                "readonly",
                "configured_class_name",
            },
        )

        # cfg_class_name is a mandatory ClassVar — always written.
        data["cfg_class_name"] = self.cfg_class_name

        # configured_class_name is written only when set (None → omitted entirely).
        if self.configured_class_name:
            data["configured_class_name"] = self.configured_class_name

        # Write to YAML file
        with open(self.cfg_file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
