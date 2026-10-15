from datetime import datetime
from enum import Enum

from pydantic import BaseModel

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogEntry(BaseModel):
    """Normalized event shared by parsers and interfaces."""

    timestamp: datetime
    level: LogLevel
    source: str
    message: str

class AnalysisResult(BaseModel):
    total_entries: int
    debug_count: int
    info_count: int
    warning_count: int
    error_count: int
    critical_count: int
    error_rate: float
    top_errors: list[tuple[str, int]]
