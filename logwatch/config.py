"""Configuration loader supporting JSON and TOML formats.

Loads user configuration from disk and deep-merges it with sensible defaults
so that every key is guaranteed to exist at runtime.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "general": {
        "log_level": "INFO",
        "date_format": "%Y-%m-%d %H:%M:%S",
    },
    "scanner": {
        "max_line_length": 10_000,
        "encoding": "utf-8",
    },
    "filters": {
        "severity": ["CRITICAL", "ERROR", "WARNING", "INFO"],
        "date_from": None,
        "date_to": None,
        "keyword_include": [],
        "keyword_exclude": [],
    },
    "alerts": {
        "enabled": False,
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "use_tls": True,
        "sender": "",
        "recipients": [],
        "threshold_errors": 10,
        "threshold_window_minutes": 5,
        "cooldown_minutes": 30,
    },
    "export": {
        "format": "csv",
        "output_dir": "./reports",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into a **copy** of *base*.

    - Dict values are merged recursively.
    - All other types in *override* replace the corresponding key in *base*.
    - Keys present in *override* but absent in *base* are added.

    Args:
        base: The base (default) dictionary.
        override: User-supplied overrides.

    Returns:
        A new dictionary with merged values.
    """
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Override configuration values with ``LOGWATCH_*`` environment variables.

    Environment variables take precedence over file-based configuration,
    allowing secrets (SMTP credentials, etc.) to live in a ``.env`` file
    rather than being committed to version control.

    Args:
        config: The merged configuration dictionary.

    Returns:
        The same dictionary with any matching env-var overrides applied.
    """
    _ENV_MAP = [
        ("LOGWATCH_SMTP_HOST", "alerts", "smtp_host", "str"),
        ("LOGWATCH_SMTP_PORT", "alerts", "smtp_port", "int"),
        ("LOGWATCH_SMTP_USER", "alerts", "smtp_user", "str"),
        ("LOGWATCH_SMTP_PASSWORD", "alerts", "smtp_password", "str"),
        ("LOGWATCH_SMTP_TLS", "alerts", "use_tls", "bool"),
        ("LOGWATCH_SENDER", "alerts", "sender", "str"),
        ("LOGWATCH_RECIPIENTS", "alerts", "recipients", "csv"),
        ("LOGWATCH_ALERT_ENABLED", "alerts", "enabled", "bool"),
        ("LOGWATCH_THRESHOLD_ERRORS", "alerts", "threshold_errors", "int"),
        ("LOGWATCH_THRESHOLD_WINDOW", "alerts", "threshold_window_minutes", "int"),
        ("LOGWATCH_COOLDOWN_MINUTES", "alerts", "cooldown_minutes", "int"),
        ("LOGWATCH_REPORT_DIR", "export", "output_dir", "str"),
    ]

    for env_key, section, key, type_hint in _ENV_MAP:
        value = os.environ.get(env_key)
        if value is None:
            continue

        config.setdefault(section, {})

        if type_hint == "bool":
            config[section][key] = value.lower() in ("true", "1", "yes")
        elif type_hint == "csv":
            config[section][key] = [
                r.strip() for r in value.split(",") if r.strip()
            ]
        elif type_hint == "int":
            try:
                config[section][key] = int(value)
            except ValueError:
                logger.warning("Invalid integer for %s: %s", env_key, value)
        else:
            config[section][key] = value

    return config


def load_config(path: str | os.PathLike | None = None) -> Dict[str, Any]:
    """Load a configuration file and merge it with :data:`DEFAULT_CONFIG`.

    The file format is auto-detected by extension:

    - ``.json`` → parsed with :mod:`json`
    - ``.toml`` → parsed with :mod:`tomllib` (Python 3.11+) or the
      ``tomli`` back-port.

    If *path* is ``None`` or the file does not exist, the defaults are
    returned unchanged.

    Args:
        path: Filesystem path to a JSON or TOML configuration file.

    Returns:
        A fully-populated configuration dictionary.

    Raises:
        ValueError: If the file extension is not ``.json`` or ``.toml``.
    """
    if path is None:
        logger.debug("No config path provided; using defaults.")
        return _apply_env_overrides(copy.deepcopy(DEFAULT_CONFIG))

    path_str = str(path)

    if not os.path.isfile(path_str):
        logger.warning("Config file not found: %s — using defaults.", path_str)
        return _apply_env_overrides(copy.deepcopy(DEFAULT_CONFIG))

    ext = os.path.splitext(path_str)[1].lower()

    if ext == ".json":
        with open(path_str, "r", encoding="utf-8") as fh:
            user_config: Dict[str, Any] = json.load(fh)
    elif ext == ".toml":
        user_config = _load_toml(path_str)
    else:
        raise ValueError(
            f"Unsupported config format '{ext}'. Use .json or .toml."
        )

    logger.info("Loaded configuration from %s", path_str)
    return _apply_env_overrides(_deep_merge(DEFAULT_CONFIG, user_config))


def _load_toml(path: str) -> Dict[str, Any]:
    """Load a TOML file using ``tomllib`` (3.11+) with ``tomli`` fallback.

    Args:
        path: Path to the TOML file.

    Returns:
        Parsed dictionary.
    """
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            raise ImportError(
                "TOML support requires Python ≥ 3.11 or the 'tomli' package. "
                "Install it with: pip install tomli"
            )

    with open(path, "rb") as fh:
        return tomllib.load(fh)
