import os
import yaml
from typing import Any, Dict


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "config.yaml",
)


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found at: {config_path}\n"
            f"Please ensure config/config.yaml exists."
        )
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg
