import random
import time
import uuid
import warnings

from pathlib import Path
from typing import Any

from cloudinary import uploader
from cloudinary.exceptions import (
    AuthorizationRequired,
    BadRequest,
    Error,
    NotAllowed,
    NotFound,
)

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage


# --------------------------------------------------
# Configuration
# --------------------------------------------------

MAX_ATTEMPTS = 3
CLOUDINARY_TIMEOUT = 30

BASE_BACKOFF = 0.5
MAX_BACKOFF = 2.0

RETRYABLE_STATUS_CODES = {
    420,
    429,
    500,
    502,
    503,
    504,
}

DEFAULT_FOLDER = "cafe_and_wifi/listings"

MAX_IMAGE_PIXELS = 40_000_000

ALLOWED_FORMATS = {
    "JPEG": {"jpg", "jpeg"},
    "PNG": {"png"},
    "WEBP": {"webp"},
    "GIF": {"gif"},
}


# --------------------------------------------------
# Image validation
# --------------------------------------------------

def validate_image_file(
    file_storage: FileStorage | None,
) -> str | None:
    """
    Verify that an uploaded file contains a valid image.

    Returns:
        None if valid.
        A human-readable error message otherwise.
    """

    if file_storage is None or not file_storage.filename:
        return None

    try:
        file_storage.stream.seek(0)

        extension = Path(file_storage.filename).suffix.lower().lstrip(".")

        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(file_storage.stream) as image:

                image_format = image.format

                if image_format is None:
                    return "No image format."

                if image_format not in ALLOWED_FORMATS:
                    return "Unsupported image format."

                if extension not in ALLOWED_FORMATS[image_format]:
                    return "The image extension does not match its contents."

                width, height = image.size

                if width * height > MAX_IMAGE_PIXELS:
                    return "Image dimensions are too large."

                image.verify()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return "Please select a valid image file."

    finally:
        file_storage.stream.seek(0)

    return None


# --------------------------------------------------
# Retry helpers
# --------------------------------------------------

def _can_retry(attempt: int) -> bool:
    return attempt < MAX_ATTEMPTS - 1


def _is_retryable(error: Error) -> bool:

    status_code = getattr(error, "http_code", None)

    # Network errors may not have an HTTP status.
    return (
        status_code is None
        or status_code in RETRYABLE_STATUS_CODES
    )


def _backoff(attempt: int) -> None:

    delay = min(
        BASE_BACKOFF * (2 ** attempt),
        MAX_BACKOFF,
    )

    delay += random.uniform(0, delay * 0.25)

    current_app.logger.info(
        "[Cloudinary] Retrying in %.2f seconds...",
        delay,
    )

    time.sleep(delay)


def _configured() -> bool:
    return bool(
        current_app.config.get("CLOUDINARY_ENABLED")
    )


# --------------------------------------------------
# Upload
# --------------------------------------------------

def upload_image_file(
    file_storage: FileStorage | None,
    folder: str = DEFAULT_FOLDER,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Upload an image to Cloudinary.

    Returns:
        (response_dict, None) on success.
        (None, error_message) on failure.
    """

    if not _configured():
        return None, "Image uploads are not configured."

    if file_storage is None or not file_storage.filename:
        return None, "No image was provided."

    # A stable ID makes retries of this upload idempotent.
    public_id = uuid.uuid4().hex

    for attempt in range(MAX_ATTEMPTS):

        attempt_number = attempt + 1

        try:
            file_storage.stream.seek(0)

            current_app.logger.info(
                "[Cloudinary] Uploading image (attempt %s/%s).",
                attempt_number,
                MAX_ATTEMPTS,
            )

            response = uploader.upload(
                file_storage.stream,
                folder=folder,
                public_id=public_id,
                resource_type="image",
                overwrite=True,
                invalidate=True,
                timeout=CLOUDINARY_TIMEOUT,
            )

            # Confirm that the identifiers required by the
            # application were returned.
            if not all(
                response.get(key)
                for key in ("secure_url", "public_id", "asset_id")
            ):
                current_app.logger.error(
                    "[Cloudinary] Upload returned incomplete metadata."
                )

                return None, "The upload service returned an invalid response."

            current_app.logger.info(
                "[Cloudinary] Image uploaded successfully."
            )

            return response, None

        except (
            AuthorizationRequired,
            BadRequest,
            NotAllowed,
        ):
            current_app.logger.exception(
                "[Cloudinary] Upload rejected."
            )

            return None, (
                "The image could not be uploaded. "
                "Please check the image and try again."
            )

        except Error as exc:

            current_app.logger.exception(
                "[Cloudinary] Upload failed (attempt %s/%s).",
                attempt_number,
                MAX_ATTEMPTS,
            )

            if (
                _is_retryable(exc)
                and _can_retry(attempt)
            ):
                _backoff(attempt)
                continue

            return None, (
                "Could not upload the image. "
                "Please try again later."
            )

    return None, "Unable to upload image."


# --------------------------------------------------
# Delete
# --------------------------------------------------

def delete_image_file(
    public_id: str | None,
) -> str | None:
    """
    Delete an image from Cloudinary.

    Returns:
        None on success.
        An error message on failure.
    """

    if not public_id:
        return None

    if not _configured():
        return "Cloudinary is not configured."

    for attempt in range(MAX_ATTEMPTS):

        attempt_number = attempt + 1

        try:
            current_app.logger.info(
                "[Cloudinary] Deleting image (attempt %s/%s).",
                attempt_number,
                MAX_ATTEMPTS,
            )

            uploader.destroy(
                public_id,
                resource_type="image",
                invalidate=True,
                timeout=CLOUDINARY_TIMEOUT,
            )

            current_app.logger.info(
                "[Cloudinary] Image deletion completed."
            )

            return None

        except NotFound:
            # Deleting an already-removed image is harmless.
            return None

        except (
            AuthorizationRequired,
            BadRequest,
            NotAllowed,
        ):
            current_app.logger.exception(
                "[Cloudinary] Image deletion rejected."
            )

            return "Unable to delete the previous image."

        except Error as exc:

            current_app.logger.exception(
                "[Cloudinary] Image deletion failed (attempt %s/%s).",
                attempt_number,
                MAX_ATTEMPTS,
            )

            if (
                _is_retryable(exc)
                and _can_retry(attempt)
            ):
                _backoff(attempt)
                continue

            return "Unable to delete the previous image."

    return "Unable to delete image."