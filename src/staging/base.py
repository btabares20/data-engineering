from abc import ABC, abstractmethod
from db.models import Raw


class Parser(ABC):
    @abstractmethod
    def parse_raw(self, raw: Raw)->dict:
        ...
