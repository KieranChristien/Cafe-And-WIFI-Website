"""Database transaction helpers for Flask routes and services."""

import logging

from flask import current_app, flash, has_app_context, has_request_context
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from web.extensions import db

logger = logging.getLogger(__name__)


def commit_session(
        *,
        success_message: str | None = None,
        error_message: str | None = "Unable to save your changes. Please try again.",
        integrity_error_message: str | None = None,
        debug_message: str = "Database transaction failed.",
        integrity_debug_message: str | None = None,
        success_category: str = "success",
        error_category: str = "error",
) -> bool:
    """Flush and commit the current session, rolling back on DB errors.

    Args:
        success_message: Optional user-facing message flashed after a successful commit.
        error_message: User-facing message for general SQLAlchemy errors. Set to None
            or an empty string to suppress the error flash.
        integrity_error_message: Optional user-facing message specifically for an
            IntegrityError. Defaults to ``error_message``. Set to an empty string to
            suppress this flash.
        debug_message: Internal log message for general database errors. Never flashed.
        integrity_debug_message: Internal log message for integrity violations.
            Defaults to ``debug_message``. Never flashed.
        success_category: Flask flash category for success_message.
        error_category: Flask flash category for database errors.

    Returns:
        True if the transaction committed; otherwise False.

    Notes:
        IntegrityError includes constraint violations such as unique, foreign-key,
        NOT NULL, and CHECK constraint failures. The database remains the authority
        for these checks; this helper does not attempt race-prone pre-checks.
        Non-SQLAlchemy programming errors are deliberately allowed to propagate.
    """

    def _flash_if_possible(message: str | None, category: str) -> None:
        # A request context is required for Flask's flash() mechanism.
        if message and has_request_context():
            flash(message, category)

    def _log_exception(message: str, *, integrity: bool = False) -> None:
        # Routes normally have an app context. The fallback keeps logging usable
        # in unusual test/CLI contexts without exposing the exception to the UI.
        active_logger = current_app.logger if has_app_context() else logger
        if integrity:
            active_logger.warning(message, exc_info=True)
        else:
            active_logger.exception(message)

    try:
        # Flush explicitly so constraint errors are caught here, before commit.
        db.session.flush()
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        _log_exception(
            integrity_debug_message or debug_message,
            integrity=True,
        )
        ui_message = (
            integrity_error_message
            if integrity_error_message is not None
            else error_message
        )
        _flash_if_possible(ui_message, error_category)
        return False

    except SQLAlchemyError:
        db.session.rollback()
        _log_exception(debug_message)
        _flash_if_possible(error_message, error_category)
        return False

    _flash_if_possible(success_message, success_category)
    return True
