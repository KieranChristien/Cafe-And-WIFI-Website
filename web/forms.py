from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileSize, FileRequired
from wtforms import IntegerField
from wtforms.fields.simple import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, URL, Optional, Email, InputRequired

# ------------------------------------------------------------------------------------------------------
# Field Lengths
# ------------------------------------------------------------------------------------------------------
NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 254
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 256
CAPTION_MAX_LENGTH = 250
ALT_TEXT_MAX_LENGTH = 150
URL_NAME_MAX_LENGTH = 20
URL_MAX_LENGTH = 2048

IMAGE_MAX_SIZE_MB = 10
THUMBNAIL_MAX_SIZE_MB = 5


# ------------------------------------------------------------------------------------------------------
# SHARED HELPERS
# ------------------------------------------------------------------------------------------------------
def _validate_length_bounds(
        min_len: int | None,
        max_len: int | None,
) -> None:
    if min_len is not None and min_len < 0:
        raise ValueError("`min_len` cannot be negative.")

    if max_len is not None and max_len < 0:
        raise ValueError("`max_len` cannot be negative.")

    if min_len is not None and max_len is not None and max_len < min_len:
        raise ValueError("`min_len` cannot be more than `max_len`.")


# ------------------------------------------------------------------------------------------------------
# REQUIRED FIELD VALIDATION
# ------------------------------------------------------------------------------------------------------
FIELD_REQUIRED = "This field is required."
RequiredValidatorType = type[DataRequired] | type[InputRequired]


def _required_message(
        message: str | None = None,
) -> str:
    return FIELD_REQUIRED if message is None else message


def required_validators(
        validator_type: RequiredValidatorType = InputRequired,
        message: str | None = None,
) -> list:
    return [
        validator_type(message=_required_message(message))
    ]


def required_render_kw(
        message: str | None = None,
) -> dict:
    return {
        "data-msg-required": _required_message(message)
    }


# ------------------------------------------------------------------------------------------------------
# STRING VALIDATION
# ------------------------------------------------------------------------------------------------------
def string_validators(min_len: int | None = None, max_len: int | None = None, required: bool = False,
                      required_message: str | None = None) -> list:
    _validate_length_bounds(min_len, max_len)

    validators: list = required_validators(DataRequired, required_message) if required else [Optional()]

    if min_len is not None:
        validators.append(Length(min=min_len, message=f"Please use at least {min_len} characters."))

    if max_len is not None:
        validators.append(Length(max=max_len, message=f"Please use {max_len} characters or fewer."))

    return validators


def string_render_kw(min_len: int | None = None, max_len: int | None = None, required: bool = False,
                     required_message: str | None = None) -> dict:
    _validate_length_bounds(min_len, max_len)

    render_kw: dict = required_render_kw(required_message) if required else {}

    if min_len is not None:
        render_kw["minlength"] = min_len
        render_kw["data-msg-too-short"] = f"Please use at least {min_len} characters."

    if max_len is not None:
        render_kw["maxlength"] = max_len
        render_kw["data-msg-too-long"] = f"Please use {max_len} characters or fewer."

    return render_kw


# ------------------------------------------------------------------------------------------------------
# EMAIL VALIDATION
# ------------------------------------------------------------------------------------------------------
EMAIL_INVALID = "Please enter a valid email address."
EMAIL_TOO_LONG = f"Please use {EMAIL_MAX_LENGTH} characters or fewer."


def email_validators(required: bool = False, required_message: str | None = None) -> list:
    validators: list = required_validators(DataRequired, required_message) if required else [Optional()]

    validators.extend([
        Email(message=EMAIL_INVALID),
        Length(max=EMAIL_MAX_LENGTH, message=EMAIL_TOO_LONG),
    ])

    return validators


def email_render_kw(required: bool = False, required_message: str | None = None) -> dict:
    render_kw: dict = required_render_kw(required_message) if required else {}
    render_kw.update({
        "type": "email",
        "maxlength": EMAIL_MAX_LENGTH,
        "data-msg-type-mismatch": EMAIL_INVALID,
        "data-msg-too-long": EMAIL_TOO_LONG,
    })

    return render_kw


# ------------------------------------------------------------------------------------------------------
# PASSWORD VALIDATION
# ------------------------------------------------------------------------------------------------------
def password_validators(required: bool = False, required_message: str | None = None) -> list:
    return string_validators(PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH, required, required_message)


def password_render_kw(required: bool = False, required_message: str | None = None) -> dict:
    return string_render_kw(PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH, required, required_message)


# ------------------------------------------------------------------------------------------------------
# FILE VALIDATION
# ------------------------------------------------------------------------------------------------------
BYTES_PER_MB = 1024 * 1024
IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
}

IMAGE_INVALID = "Please submit a valid image."
FILE_REQUIRED = "This file is required."
FILE_TOO_LARGE = "File must be {max_size_mb}MB or smaller."


def file_validators(max_size_mb: int | None = None, is_image: bool = False, required: bool = False,
                    required_message: str | None = None) -> list:
    if max_size_mb is not None and max_size_mb < 0:
        raise ValueError("`max_size_mb` cannot be negative.")

    validators: list = [FileRequired(
        message=FILE_REQUIRED if required_message is None else required_message,
    )] if required else [Optional()]

    if max_size_mb is not None:
        validators.append(
            FileSize(
                max_size=max_size_mb * BYTES_PER_MB,
                message=FILE_TOO_LARGE.format(max_size_mb=max_size_mb),
            )
        )

    if is_image:
        validators.append(
            FileAllowed(
                IMAGE_EXTENSIONS,
                message=IMAGE_INVALID,
            )
        )

    return validators


def file_render_kw(max_size_mb: int | None = None, is_image: bool = False, required: bool = False,
                   required_message: str | None = None) -> dict:
    if max_size_mb is not None and max_size_mb < 0:
        raise ValueError("`max_size_mb` cannot be negative.")

    render_kw: dict = required_render_kw(
        FILE_REQUIRED if required_message is None else required_message,
    ) if required else {}

    if is_image:
        render_kw["accept"] = ",".join(
            f".{extension}" for extension in IMAGE_EXTENSIONS
        )
        render_kw["data-msg-invalid-file"] = IMAGE_INVALID

    if max_size_mb is not None:
        render_kw["data-max-size-bytes"] = max_size_mb * BYTES_PER_MB
        render_kw["data-msg-file-too-large"] = FILE_TOO_LARGE.format(
            max_size_mb=max_size_mb
        )

    return render_kw


# ------------------------------------------------------------------------------------------------------
# URL VALIDATION
# ------------------------------------------------------------------------------------------------------
URL_INVALID = "Please enter a valid url."
URL_TOO_LONG = f"Please use {URL_MAX_LENGTH} characters or fewer."


def url_validators(required: bool = False, required_message: str | None = None) -> list:
    validators: list = required_validators(DataRequired, required_message) if required else [Optional()]

    validators.extend([
        URL(message=URL_INVALID),
        Length(max=URL_MAX_LENGTH, message=URL_TOO_LONG),
    ])

    return validators


def url_render_kw(required: bool = False, required_message: str | None = None) -> dict:
    render_kw: dict = required_render_kw(required_message) if required else {}

    render_kw.update({
        "type": "url",
        "maxlength": URL_MAX_LENGTH,
        "data-msg-type-mismatch": URL_INVALID,
        "data-msg-too-long": URL_TOO_LONG,
    })

    return render_kw


# Create a form to submit café reviews
class CafeReviewForm(FlaskForm):
    name = StringField(
        "Name",
        validators=string_validators(max_len=50, required=True, required_message="Please enter your name."),
        render_kw=string_render_kw(max_len=50, required=True, required_message="Please enter your name."),
    )

    rating = IntegerField(
        "Rating",
        default=5,
        validators=[
            *required_validators(
                InputRequired,
                "Please rate the café."
            ),
            NumberRange(min=1, max=5),
        ],
        render_kw={
            **required_render_kw("Please rate the café."),
            "type": "range",
            "min": 1,
            "max": 5,
            "step": 1,
        },
    )

    body = TextAreaField(
        "Your review",
        validators=string_validators(max_len=500, required=True, required_message="Tell people what it's like."),
        render_kw=string_render_kw(max_len=500, required=True, required_message="Tell people what it's like."),
    )

    submit = SubmitField("Post review")
