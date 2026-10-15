"""Public error types shared by input adapters."""


class LogParseError(ValueError):
    """A malformed record, optionally located within an input stream."""

    def __init__(self, message: str, *, source: str | None = None,
                 line_number: int | None = None):
        self.source = source
        self.line_number = line_number
        location = f"{source}:{line_number}: " if source is not None else ""
        super().__init__(location + message)
