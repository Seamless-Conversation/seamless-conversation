import logging

logger = logging.getLogger(__name__)

def load_prompt(file_path: str) -> str:
    """Loads specified file and returns its text contents"""
    try:
        with open(file_path, mode='r') as file:
            prompt = file.read()
    except IOError as ioe:
        logger.error(f"Error opening the prompt file {file_path}: {ioe}")
    return prompt