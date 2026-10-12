"""教案 AI 候选生成（固定报告 + 冻结输入）。"""
from .preparation import PreparedGeneration
from .service import LessonGenerationService

__all__ = ["LessonGenerationService", "PreparedGeneration"]
