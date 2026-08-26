from datetime import datetime
from enum import Enum

from pydantic import BaseModel

class LogLevel(str,Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogEntry(BaseModel):
    timestamp : datetime
    level : LogLevel
    source : str
    message : str