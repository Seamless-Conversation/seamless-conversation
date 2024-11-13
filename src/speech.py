from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Union

class SpeechType(Enum):
    USER = "user"
    LLM = "llm"