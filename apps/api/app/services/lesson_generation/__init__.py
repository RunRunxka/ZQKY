"""B5 fixed-report lesson proposals; consumers use the frozen public port."""
from .preparation import PreparedGeneration
from .service import LessonGenerationService

__all__ = ["LessonGenerationService", "PreparedGeneration"]
