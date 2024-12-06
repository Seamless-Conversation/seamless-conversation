import yaml
from .settings import AppConfig
import logging

logger = logging.getLogger(__name__)

def load_config(path: str) -> AppConfig:
    try:
        with open(path, 'r') as f:
            config_dict = yaml.safe_load(f)
        return AppConfig(**config_dict)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise