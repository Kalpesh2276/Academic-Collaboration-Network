"""Consistent JSON error responses.

Every error returned by the API has the shape
    {"error": {"code": "<MACHINE_CODE>", "message": "<human readable>", "details": ...}}
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from neo4j.exceptions import AuthError, ClientError, ConstraintError, ServiceUnavailable, SessionExpired
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("acn.errors")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


class NotFound(ApiError):
    def __init__(self, entity: str, entity_id: str):
        super().__init__(404, "NOT_FOUND", f"{entity} '{entity_id}' was not found.", {"entity": entity, "id": entity_id})


class Conflict(ApiError):
    def __init__(self, message: str, details: Any = None):
        super().__init__(409, "CONFLICT", message, details)


class BadRequest(ApiError):
    def __init__(self, message: str, details: Any = None):
        super().__init__(400, "BAD_REQUEST", message, details)


def _body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in err.get("loc", []) if p != "body"), "message": err.get("msg")}
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content=_body("VALIDATION_ERROR", "Invalid input.", details))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content=_body("HTTP_ERROR", str(exc.detail)))

    @app.exception_handler(ConstraintError)
    async def _constraint(_: Request, exc: ConstraintError):
        return JSONResponse(
            status_code=409,
            content=_body("CONSTRAINT_VIOLATION", "A record with this unique identifier already exists.", exc.message),
        )

    @app.exception_handler(AuthError)
    async def _auth(_: Request, exc: AuthError):
        log.error("Neo4j authentication failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content=_body("DATABASE_AUTH_FAILED", "Could not authenticate with Neo4j. Check NEO4J_USER / NEO4J_PASSWORD."),
        )

    @app.exception_handler(ServiceUnavailable)
    async def _unavailable(_: Request, exc: ServiceUnavailable):
        log.error("Neo4j unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content=_body("DATABASE_UNAVAILABLE", "The Neo4j database is not reachable. Is it running and is NEO4J_URI correct?"),
        )

    @app.exception_handler(SessionExpired)
    async def _expired(_: Request, exc: SessionExpired):
        log.error("Neo4j session expired: %s", exc)
        return JSONResponse(status_code=503, content=_body("DATABASE_UNAVAILABLE", "The Neo4j session expired. Retry."))

    @app.exception_handler(ClientError)
    async def _client(_: Request, exc: ClientError):
        log.exception("Cypher client error")
        return JSONResponse(status_code=500, content=_body("CYPHER_ERROR", "The database rejected a query.", exc.message))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(status_code=500, content=_body("INTERNAL_ERROR", "Unexpected server error."))
