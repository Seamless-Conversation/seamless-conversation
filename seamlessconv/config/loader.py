import logging
import yaml
from .settings import AppConfig

logger = logging.getLogger(__name__)

def load_config(path: str) -> AppConfig:
    """
    Load configuration from a YAML file and return an AppConfig object.

    Args:
        path (str): Path to the configuration file.

    Returns:
        AppConfig: An instance of AppConfig populated with the loaded configuration.

    """
    try:
        with open(path, 'r', encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)
        return AppConfig(**config_dict)
    except Exception as e:
        logger.error("Failed to load configuration: %s", e)
        raise
