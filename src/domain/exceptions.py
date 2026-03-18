"""
Domain exceptions for the POP monitoring application.
"""


class PopDataError(Exception):
    """Base exception for POP data operations."""


class PopNotFoundError(PopDataError):
    """Raised when a POP or region cannot be found."""

    def __init__(self, region: str, pop: str = ""):
        self.region = region
        self.pop = pop
        msg = f"Region '{region}'" + (f", POP '{pop}'" if pop else "") + " not found"
        super().__init__(msg)


class DatabaseError(PopDataError):
    """Raised when a database operation fails."""


class DataCleaningError(PopDataError):
    """Raised when data cleaning/normalization fails."""


class MergeError(PopDataError):
    """Raised when data merging fails."""


class ValidationError(PopDataError):
    """Raised when data validation fails."""

    def __init__(self, missing_columns: list[str] | None = None, message: str = ""):
        self.missing_columns = missing_columns or []
        msg = message or f"Missing required columns: {', '.join(self.missing_columns)}"
        super().__init__(msg)
