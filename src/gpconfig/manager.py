"""GPConfigManager - Central configuration manager for gpconfig."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Type, TypeVar, Union

import yaml

if TYPE_CHECKING:
    from gpconfig.config import GPConfig

from gpconfig.exceptions import (
    ConfigFolderError,
    ConfigNotFoundError,
    ConfigValidationError,
    RegistrationError,
)

T = TypeVar("T")


class GPConfigFolder:
    """Represent a subfolder in the config folder hierarchy.

    This class provides convenient access to configs within a specific folder.

    Attributes:
        path: Relative path from cfg_folder (dot notation, e.g., "llm.providers").
    """

    def __init__(self, manager: "GPConfigManager", relative_path: str):
        """Initialize GPConfigFolder.

        Args:
            manager: The GPConfigManager instance.
            relative_path: Relative path from cfg_folder using dot notation.
        """
        self._manager = manager
        self._relative_path = relative_path

    @property
    def path(self) -> str:
        """Get the relative path of this folder."""
        return self._relative_path

    def get_config(
        self, path: str, config_cls: Optional[Type[T]] = None
    ) -> Union[T, Any]:
        """Get a config object or value from this folder.

        Args:
            path: Config path relative to this folder (e.g., "api" or "nested.config").
            config_cls: Optional GPConfig subclass to use for loading.

        Returns:
            GPConfig instance, GPConfigFolder, or config value.
        """
        full_path = f"{self._relative_path}.{path}" if self._relative_path else path
        return self._manager.get_config(full_path, config_cls)

    def get_object(self, path: str) -> Any:
        """Get a configurable object instance from this folder.

        Args:
            path: Config path relative to this folder.

        Returns:
            A new instance of the configured GPConfigurable subclass.
        """
        full_path = f"{self._relative_path}.{path}" if self._relative_path else path
        return self._manager.get_object(full_path)

    def list_configs(self) -> List[str]:
        """List all config objects in this folder.

        Returns:
            List of object names (config names and subfolder names).
        """
        return self._manager.list_configs(self._relative_path)


class GPConfigManager:
    """Central manager for configuration management.

    This class handles initialization, config folder resolution, and provides
    access to configuration data.

    Attributes:
        project_name: Name of the project using gpconfig.
        cfg_folder: Path to the resolved configuration folder.
        global_env: Dictionary containing global environment configuration.

    Config Folder Search Rules:
        1. Explicit parameter - cfg_folder argument if provided
        2. Environment variable - {PROJECT_NAME}_CFG_PATH (uppercase)
        3. User home subfolder - ~/.{project_name}/

    A valid config folder must contain global_env.yaml.
    """

    # Class-level registry: cfg_class_name -> GPConfig subclass
    _config_classes: dict[str, Type[Any]] = {}
    # Class-level registry: configurable class name -> GPConfigurable subclass
    _configurable_classes: dict[str, Type[Any]] = {}

    def __init__(self, project_name: str, cfg_folder: Optional[Path | str] = None):
        """Initialize GPConfigManager.

        Args:
            project_name: Name of the project.
            cfg_folder: Optional explicit path to config folder.
                       If not provided, will search using the resolution rules.

        Raises:
            ConfigFolderError: If config folder doesn't exist or lacks global_env.yaml.
        """
        self._project_name = project_name
        self._cfg_folder = self._resolve_cfg_folder(project_name, cfg_folder)
        self._global_env = self._load_global_env()
        self._config_cache: dict[str, Any] = {}
        self._folder_cache: dict[str, GPConfigFolder] = {}

    @property
    def project_name(self) -> str:
        """Get the project name."""
        return self._project_name

    @property
    def cfg_folder(self) -> Path:
        """Get the config folder path."""
        return self._cfg_folder

    @property
    def global_env(self) -> dict:
        """Get the global environment configuration."""
        return self._global_env

    def _resolve_cfg_folder(
        self, project_name: str, cfg_folder: Optional[Path | str]
    ) -> Path:
        """Resolve the config folder using search rules.

        Args:
            project_name: Name of the project.
            cfg_folder: Optional explicit path to config folder.

        Returns:
            Resolved Path to config folder.

        Raises:
            ConfigFolderError: If no valid config folder can be found.
        """
        # Rule 1: Explicit parameter
        if cfg_folder is not None:
            cfg_path = Path(cfg_folder).resolve()
            self._validate_cfg_folder(cfg_path, "explicit parameter")
            return cfg_path

        # Rule 2: Environment variable
        env_var_name = f"{project_name.upper()}_CFG_PATH"
        import os

        env_path = os.environ.get(env_var_name)
        if env_path:
            cfg_path = Path(env_path).resolve()
            self._validate_cfg_folder(cfg_path, f"environment variable {env_var_name}")
            return cfg_path

        # Rule 3: User home subfolder
        home_path = Path.home() / f".{project_name}"
        if home_path.exists():
            cfg_path = home_path.resolve()
            self._validate_cfg_folder(cfg_path, f"home folder {home_path}")
            return cfg_path

        # No valid folder found
        raise ConfigFolderError(
            f"Could not find valid config folder for project '{project_name}'. "
            f"Searched: explicit parameter, environment variable {env_var_name}, "
            f"and home folder {home_path}"
        )

    def _validate_cfg_folder(self, cfg_path: Path, source: str) -> None:
        """Validate that the config folder is valid.

        A valid config folder must:
        - Exist as a directory
        - Contain global_env.yaml

        Args:
            cfg_path: Path to validate.
            source: Description of where the path came from (for error messages).

        Raises:
            ConfigFolderError: If the folder is invalid.
        """
        if not cfg_path.exists():
            raise ConfigFolderError(
                f"Config folder does not exist: {cfg_path} (from {source})"
            )

        if not cfg_path.is_dir():
            raise ConfigFolderError(
                f"Config folder path is not a directory: {cfg_path} (from {source})"
            )

        global_env_path = cfg_path / "global_env.yaml"
        if not global_env_path.exists():
            raise ConfigFolderError(
                f"Config folder must contain global_env.yaml: {cfg_path} (from {source})"
            )

    def _load_global_env(self) -> dict:
        """Load global_env.yaml into a dictionary.

        Returns:
            Dictionary with global environment configuration.
            Returns empty dict if file is empty or contains only comments.
        """
        global_env_path = self._cfg_folder / "global_env.yaml"

        with open(global_env_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)

        # yaml.safe_load returns None for empty files or files with only comments
        return content if content is not None else {}

    def _parse_path(self, path: str) -> tuple[Path, Optional[str]]:
        """
        Parse a config path into (file_path, optional_key).

        Args:
            path: Config path string

        Returns:
            Tuple of (yaml_file_path, optional_key_path)

        Raises:
            ConfigNotFoundError: If the path cannot be resolved
        """
        from gpconfig.exceptions import ConfigNotFoundError

        parts = path.split(".")

        # Strip optional project name prefix
        if parts[0] == self._project_name:
            parts = parts[1:]

        if not parts:
            raise ConfigNotFoundError(path, "Empty config path")

        # Handle global_env specially
        if parts[0] == "global_env":
            if len(parts) == 1:
                raise ConfigNotFoundError(
                    path, "global_env requires a key path (e.g., 'global_env.debug')"
                )
            return (self._cfg_folder / "global_env.yaml", ".".join(parts[1:]))

        # Try to find the config file by progressively treating
        # trailing parts as keys if file not found
        for i in range(len(parts), 0, -1):
            folder_parts = parts[: i - 1]
            file_part = parts[i - 1]
            key_parts = parts[i:]

            candidate_path = self._cfg_folder
            for fp in folder_parts:
                candidate_path = candidate_path / fp

            yaml_path = candidate_path / f"{file_part}.yaml"
            if yaml_path.exists():
                return (yaml_path, ".".join(key_parts) if key_parts else None)

        raise ConfigNotFoundError(path)

    def _check_folder_exists(self, path: str) -> tuple[bool, Path]:
        """Check if a folder exists at the given path.

        Args:
            path: Config path (dot notation).

        Returns:
            Tuple of (exists, full_path).
        """
        parts = path.split(".")

        # Strip optional project name prefix
        if parts[0] == self._project_name:
            parts = parts[1:]

        if not parts:
            return (False, Path())

        folder_path = self._cfg_folder
        for part in parts:
            folder_path = folder_path / part

        return (folder_path.is_dir(), folder_path)

    def _get_or_create_folder(self, path: str) -> GPConfigFolder:
        """Get or create a cached GPConfigFolder for the given path.

        Args:
            path: Config path (dot notation), optionally prefixed with project name.

        Returns:
            A cached GPConfigFolder instance for the path.
        """
        # Normalize path
        parts = path.split(".")
        if parts[0] == self._project_name:
            parts = parts[1:]
        normalized_path = ".".join(parts)

        if normalized_path not in self._folder_cache:
            self._folder_cache[normalized_path] = GPConfigFolder(self, normalized_path)

        return self._folder_cache[normalized_path]

    def get_config(
        self,
        path: str,
        config_cls: Optional[Type[T]] = None,
        *,
        _force_file: bool = False,
    ) -> Union[T, Any]:
        """
        Get a config object, folder, or a specific config value.

        Args:
            path: Config path (e.g., "cfg_name" or "cfg_class.cfg_name" or "cfg.path.key")
            config_cls: Optional GPConfig subclass to use for loading.
                       If not provided, will try to auto-detect from cfg_class_name in the file.

        Returns:
            - GPConfigFolder if path points to a folder (and no config_cls, or no file exists)
            - GPConfig instance if path points to a config file
            - Config value if path points to a specific key

        Raises:
            ConfigNotFoundError: If the path doesn't exist
            ConfigValidationError: If the config fails validation
        """
        from pydantic import ValidationError

        # First check if folder exists
        folder_exists, folder_path = self._check_folder_exists(path)

        # Try to parse as file path
        try:
            file_path, key = self._parse_path(path)
            file_exists = file_path.exists()
        except ConfigNotFoundError:
            file_path = None
            key = None
            file_exists = False

        # Determine what to return based on existence and config_cls
        if file_exists and folder_exists:
            # Both exist: config_cls or _force_file determines priority
            if config_cls is not None or _force_file:
                # File priority
                pass  # Continue with file loading below
            else:
                # Folder priority
                return self._get_or_create_folder(path)
        elif folder_exists and not file_exists:
            # Only folder exists
            return self._get_or_create_folder(path)
        elif not file_exists and not folder_exists:
            # Neither exists
            raise ConfigNotFoundError(path)

        # File loading logic (existing code)
        # Generate cache key
        cache_key = str(file_path)

        # Handle global_env key access
        if file_path.name == "global_env.yaml" and key:
            return self._get_nested_value(self._global_env, key, path)

        # Load or retrieve cached config
        if cache_key not in self._config_cache:
            # Load raw data first
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}

            if key:
                # Key access - just return the value
                return self._get_nested_value(raw_data, key, path)

            # Auto-detect config class from cfg_class_name if not provided
            if config_cls is None:
                cfg_class_name = raw_data.get("cfg_class_name")
                if cfg_class_name and cfg_class_name in self._config_classes:
                    config_cls = self._config_classes[cfg_class_name]

            if config_cls is None:
                # No config class found - return raw dict
                return raw_data

            try:
                # Remove cfg_class_name from data before passing to config class
                # since it's a ClassVar, not an instance field
                data_for_config = {
                    k: v for k, v in raw_data.items() if k != "cfg_class_name"
                }
                config = self._load_config(file_path, config_cls, data_for_config)
            except ValidationError as e:
                raise ConfigValidationError(path, e)

            self._config_cache[cache_key] = config

        config = self._config_cache[cache_key]

        if key:
            return self._get_nested_value(config.model_dump(), key, path)

        return config

    def _load_config(
        self, file_path: Path, config_cls: Type[T], data: Optional[dict] = None
    ) -> T:
        """Load a config from a YAML file.

        Args:
            file_path: Path to the YAML file.
            config_cls: The GPConfig subclass to instantiate.
            data: Optional pre-loaded data dict. If None, will load from file.

        Returns:
            Configured GPConfig instance.
        """
        if data is None:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        config = config_cls(**data)
        config.name = file_path.stem
        config.cfg_file_path = file_path
        return config

    def _get_nested_value(self, data: dict, key_path: str, full_path: str) -> Any:
        """Get a nested value from a dict using dot notation."""
        keys = key_path.split(".")
        current = data

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                raise ConfigNotFoundError(
                    full_path, f"Key '{key}' not found in path '{full_path}'"
                )
            current = current[key]

        return current

    @classmethod
    def register_config_class(cls, config_cls: Type[Any]) -> None:
        """Register a config class by its cfg_class_name.

        This method registers config classes that don't configure specific objects,
        or can be called independently before register_configurable_class.

        Args:
            config_cls: The GPConfig subclass to register.

        Raises:
            RegistrationError: If a class with the same cfg_class_name is already registered.
        """
        cfg_class_name = config_cls.cfg_class_name
        if cfg_class_name in cls._config_classes:
            # Idempotent: allow re-registration of same class
            if cls._config_classes[cfg_class_name] is config_cls:
                return
            raise RegistrationError(
                f"Config class name '{cfg_class_name}' is already registered "
                f"with a different class"
            )
        cls._config_classes[cfg_class_name] = config_cls

    @classmethod
    def register_configurable_class(cls, configurable_cls: Type[Any]) -> None:
        """Register a GPConfigurable subclass by its class name.

        This method registers configurable classes that can be instantiated
        from config files that specify configured_class_name.

        Args:
            configurable_cls: The GPConfigurable subclass to register.

        Raises:
            RegistrationError: If a different class with the same name is already registered.
        """
        class_name = configurable_cls.__name__
        if class_name in cls._configurable_classes:
            # Idempotent: allow re-registration of same class
            if cls._configurable_classes[class_name] is configurable_cls:
                return
            raise RegistrationError(
                f"Configurable class name '{class_name}' is already registered "
                f"with a different class"
            )
        cls._configurable_classes[class_name] = configurable_cls

    def get_object(self, path: str) -> Any:
        """Get a configurable object instance from a config path.

        This method:
        1. Loads the config using get_config (auto-detects class from cfg_class_name)
        2. Reads configured_class_name from the config instance
        3. Looks up the configurable class in _configurable_classes
        4. Creates a new instance (no caching)

        Args:
            path: Config path (e.g., "database" or "services.api").

        Returns:
            A new instance of the configured GPConfigurable subclass.

        Raises:
            RegistrationError: If the configured_class_name is missing or not registered.
            ConfigNotFoundError: If the config path doesn't exist.
        """
        # Load the config (will auto-detect class from cfg_class_name)
        # Use _force_file=True to ensure we get file even when folder exists
        config = self.get_config(path, _force_file=True)

        # If config is a dict, we can still proceed if it has configured_class_name
        if isinstance(config, dict):
            class_name = config.get("configured_class_name")
            if not class_name:
                raise RegistrationError(
                    f"Config at path '{path}' was loaded as dict (no registered config class). "
                    f"Use register_config_class() first, or add 'configured_class_name' to the config."
                )
        else:
            # Get the configured_class_name from the config instance
            class_name = config.configured_class_name

            if not class_name:
                raise RegistrationError(
                    f"Config at path '{path}' has no configured_class_name. "
                    f"Add 'configured_class_name' to the config file."
                )

        if class_name not in self._configurable_classes:
            raise RegistrationError(
                f"Configured class '{class_name}' not registered for config at '{path}'. "
                f"Use register_configurable_class() to register it."
            )

        configurable_cls = self._configurable_classes[class_name]
        return configurable_cls(config)

    def list_configs(self, path: str = "") -> list[str]:
        """List all config objects in a folder.

        This method returns names of YAML config files and subfolders,
        excluding global_env.yaml.

        Args:
            path: Optional folder path relative to cfg_folder.
                  Empty string means root folder.

        Returns:
            List of object names (config names without .yaml extension, and folder names).

        Raises:
            ConfigNotFoundError: If the folder doesn't exist.
        """
        if path:
            # Convert dot notation to path separators
            folder_path = self._cfg_folder / Path(
                path.replace(".", "/") if "." in path else path
            )
        else:
            folder_path = self._cfg_folder

        if not folder_path.exists() or not folder_path.is_dir():
            raise ConfigNotFoundError(path or "/", f"Folder '{path}' does not exist")

        items = []
        for item in folder_path.iterdir():
            # Skip global_env.yaml
            if item.name == "global_env.yaml":
                continue

            if item.is_file() and item.suffix == ".yaml":
                # Add config name without extension
                items.append(item.stem)
            elif item.is_dir():
                # Add folder name
                items.append(item.name)

        return sorted(items)

    def save(self, config: "GPConfig", path: Optional[str] = None) -> None:
        """Save a GPConfig instance to a config file.

        This method determines the file path using:
        1. If `path` is provided: use it as relative path from cfg_folder
        2. Otherwise: use config's default_cfg_path + name

        The config's cfg_file_path will be set before saving.

        Args:
            config: The GPConfig instance to save.
            path: Optional relative path from cfg_folder (e.g., "cache/redis" or "database").
                  If not provided, uses config.default_cfg_path + config.name.

        Raises:
            ValueError: If config.name is empty or path cannot be determined.
            ConfigReadonlyError: If config.readonly is True.
        """
        from gpconfig.config import GPConfig
        from gpconfig.exceptions import ConfigReadonlyError

        if not isinstance(config, GPConfig):
            raise TypeError(f"Expected GPConfig instance, got {type(config).__name__}")

        if config.readonly:
            raise ConfigReadonlyError(config.name or "unnamed")

        if not config.name:
            raise ValueError(
                "Config must have a non-empty 'name' attribute to be saved"
            )

        # Determine the file path
        if path is not None:
            # Use provided relative path
            # Normalize path: remove leading slashes, convert dots to slashes
            relative_path = path.lstrip("/\\").replace(".", "/")
            file_path = self._cfg_folder / f"{relative_path}.yaml"
        else:
            # Use default_cfg_path + name
            default_path = config.default_cfg_path or ""
            # Normalize default_path: remove leading/trailing slashes
            default_path = default_path.strip("/\\")

            if default_path:
                file_path = self._cfg_folder / default_path / f"{config.name}.yaml"
            else:
                file_path = self._cfg_folder / f"{config.name}.yaml"

        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Set the config's file path
        config.cfg_file_path = file_path

        # Call the config's save method
        config.save()

        # Update cache with the new config
        cache_key = str(file_path)
        self._config_cache[cache_key] = config

    @classmethod
    def make_new_project_config_folder(
        cls,
        project_name: str,
        cfgs: List["GPConfig"],
        global_env: Optional[dict] = None,
        cfg_folder_path: Optional[str | Path] = None,
    ) -> Path:
        """Create a new project configuration folder with initial configs.

        Args:
            project_name: Name of the project.
            cfgs: List of GPConfig instances to save. Each must have a non-empty 'name'.
            global_env: Optional dictionary for global_env.yaml content.
            cfg_folder_path: Optional explicit path for the config folder.

        Returns:
            Path to the created configuration folder.

        Raises:
            ConfigFolderError: If the config folder already exists.
            ValueError: If any config in cfgs has an empty 'name'.
            ConfigReadonlyError: If any config in cfgs has readonly=True.
        """
        from gpconfig.config import GPConfig
        from gpconfig.exceptions import ConfigReadonlyError
        import os

        # Resolve folder path
        if cfg_folder_path is not None:
            folder_path = Path(cfg_folder_path).resolve()
        else:
            # Try environment variable
            env_var_name = f"{project_name.upper()}_CFG_PATH"
            env_path = os.environ.get(env_var_name)
            if env_path:
                folder_path = Path(env_path).resolve()
            else:
                # Fallback to home directory
                folder_path = Path.home() / f".{project_name}"

        # Check if folder already exists
        if folder_path.exists():
            raise ConfigFolderError(f"Config folder already exists: {folder_path}")

        # Create folder
        folder_path.mkdir(parents=True, exist_ok=False)

        # Create global_env.yaml
        global_env_path = folder_path / "global_env.yaml"
        with open(global_env_path, "w", encoding="utf-8") as f:
            yaml.dump(global_env or {}, f, default_flow_style=False, allow_unicode=True)

        # Validate and save configs
        for config in cfgs:
            if not isinstance(config, GPConfig):
                raise TypeError(
                    f"Expected GPConfig instance, got {type(config).__name__}"
                )

            if not config.name:
                raise ValueError(
                    f"Config of type '{type(config).__name__}' has empty 'name' attribute. "
                    "All configs must have a non-empty 'name' to be saved."
                )

            if config.readonly:
                raise ConfigReadonlyError(config.name)

            # Determine file path from default_cfg_path + name
            default_path = config.default_cfg_path or ""
            default_path = default_path.strip("/\\")

            if default_path:
                file_path = folder_path / default_path / f"{config.name}.yaml"
            else:
                file_path = folder_path / f"{config.name}.yaml"

            # Create subdirectories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Set file path and save
            config.cfg_file_path = file_path
            config.save()

        return folder_path
