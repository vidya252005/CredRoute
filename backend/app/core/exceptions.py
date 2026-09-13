from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.request_context import current_request_id


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


async def app_error_handler(request: Request, exc: AppError):
    request_id = current_request_id()
    if request_id == "-":
        request_id = request.headers.get("X-Request-Id") or request.headers.get("X-Request-ID") or "unknown"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
        headers={"X-Request-Id": request_id},
    )


def http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
