from abc import ABC, abstractmethod
from pathlib import Path
from app.models.canonical import CanonicalRateSheet

class BaseParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: Path, filename: str) -> bool:
        pass

    @abstractmethod
    def parse(self, file_path: Path, job_id: str) -> CanonicalRateSheet:
        pass
