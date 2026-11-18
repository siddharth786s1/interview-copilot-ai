"""
Application-level exceptions with structured context.
"""
from fastapi import HTTPException, status


class AppError(Exception):
    """Base application error."""
    def __init__(self, message: str, code: str = "APP_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(f"{resource} '{resource_id}' not found", "NOT_FOUND")


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class ProviderError(AppError):
    def __init__(self, provider: str, message: str):
        super().__init__(f"Provider '{provider}' error: {message}", "PROVIDER_ERROR")


class StorageError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "STORAGE_ERROR")


def raise_not_found(resource: str, resource_id: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "NOT_FOUND", "message": f"{resource} '{resource_id}' not found"},
    )
