from abc import ABC, abstractmethod
from typing import List, Dict

class LLMProvider(ABC):
    @abstractmethod
    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        pass

    @abstractmethod
    def setup(self) -> None:
        pass