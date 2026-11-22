import phonenumbers
import pycountry
import re

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileSize, FileRequired
from phonenumbers import NumberParseException
from typing import Literal, NewType, Sequence
from wtforms import BooleanField, FieldList, Form, FormField, IntegerField, SelectField, TimeField
from wtforms.fields.simple import StringField, TextAreaField, SubmitField
from wtforms.validators import (DataRequired, Email, InputRequired, Length, NumberRange, Optional, Regexp, URL,
                                ValidationError)
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

# ------------------------------------------------------------------------------------------------------
# Field Lengths
# ------------------------------------------------------------------------------------------------------
PHONE_MAX_LENGTH = 32
EMAIL_MAX_LENGTH = 254
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 256
URL_MAX_LENGTH = 2048

# ------------------------------------------------------------------------------------------------------
# Auto-Complete
# ------------------------------------------------------------------------------------------------------
AutoCompleteToken = Literal[
    # Name
    "name",
    "honorific-prefix",
    "given-name",
    "additional-name",
    "family-name",
    "honorific-suffix",
    "nickname",

        # Account
    "username",
    "new-password",
    "current-password",
    "one-time-code",

        # Organisation
    "organization-title",
    "organization",

        # Contact
    "email",
    "impp",

        # Phone
    "tel",
    "tel-country-code",
    "tel-national",
    "tel-area-code",
    "tel-local",
    "tel-local-prefix",
    "tel-local-suffix",
    "tel-extension",

        # Address
    "street-address",
    "address-line1",
    "address-line2",
    "address-line3",
    "address-level4",
    "address-level3",
    "address-level2",
    "address-level1",
    "postal-code",
    "country",
    "country-name",

        # Credit card
    "cc-name",
    "cc-given-name",
    "cc-additional-name",
    "cc-family-name",
    "cc-number",
    "cc-exp",
    "cc-exp-month",
    "cc-exp-year",
    "cc-csc",
    "cc-type",

        # Transactions
    "transaction-currency",
    "transaction-amount",

        # Other
    "language",
    "bday",
    "bday-day",
    "bday-month",
    "bday-year",
    "sex",
    "url",
    "photo",

        # Web authentication
    "webauthn",

        # Grouping
    "shipping",
    "billing",

        # Contact types
    "home",
    "work",
    "mobile",
    "fax",
    "pager",
]

SectionToken = NewType("SectionToken", str)

AutocompletePart = AutoCompleteToken | SectionToken


# ------------------------------------------------------------------------------------------------------
# SHARED HELPERS
# ------------------------------------------------------------------------------------------------------
def section_token(name: str) -> SectionToken:
    if not re.fullmatch(r"[a-zA-Z0-9]+", name):
        raise ValueError(
            "Section names must contain only letters and numbers."
        )

    return SectionToken(f"section-{name}")


def strip_string(value):
    """Remove leading and trailing whitespace from string fields."""
    return value.strip() if isinstance(value, str) else value


def validate_length_bounds(
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
        "required": True,
        "data-msg-required": _required_message(message),
    }


# ------------------------------------------------------------------------------------------------------
# STRING VALIDATION
# ------------------------------------------------------------------------------------------------------
def string_validators(
        min_len: int | None = None,
        max_len: int | None = None,
        required: bool = False,
        required_message: str | None = None
) -> list:
    validate_length_bounds(min_len, max_len)

    validators: list = required_validators(DataRequired, required_message) if required else [Optional()]

    if min_len is not None:
        validators.append(Length(min=min_len, message=f"Please use at least {min_len} characters."))

    if max_len is not None:
        validators.append(Length(max=max_len, message=f"Please use {max_len} characters or fewer."))

    return validators


def string_render_kw(
        min_len: int | None = None,
        max_len: int | None = None,
        required: bool = False,
        required_message: str | None = None,
        autocomplete: Sequence[AutocompletePart] | Literal["on", "off"] | None = None,
) -> dict:
    validate_length_bounds(min_len, max_len)

    render_kw: dict = required_render_kw(required_message) if required else {}

    if min_len is not None:
        render_kw["minlength"] = min_len
        render_kw["data-msg-too-short"] = f"Please use at least {min_len} characters."

    if max_len is not None:
        render_kw["maxlength"] = max_len
        render_kw["data-msg-too-long"] = f"Please use {max_len} characters or fewer."

    if autocomplete is not None:
        render_kw["autocomplete"] = (
            autocomplete
            if isinstance(autocomplete, str)
            else " ".join(map(str, autocomplete))
        )

    return render_kw


# ------------------------------------------------------------------------------------------------------
# RANGE VALIDATION
# ------------------------------------------------------------------------------------------------------
RATING_RANGE_INVALID = "Please choose a rating between 1 and 5."


def range_validators(
        min_value: int | None = None,
        max_value: int | None = None,
        required: bool = False,
        required_message: str | None = None
) -> list:
    validate_length_bounds(min_value, max_value)

    validators: list = required_validators(InputRequired, required_message) if required else [Optional()]

    if min_value is not None:
        validators.append(NumberRange(min=min_value, message=f"Please use at least {min_value} characters."))

    if max_value is not None:
        validators.append(NumberRange(max=max_value, message=f"Please use {max_value} characters or fewer."))

    return validators


def range_render_kw(
        min_value: int | None = None,
        max_value: int | None = None,
        step: int | None = None,
        required: bool = False,
        required_message: str | None = None,
        autocomplete: Sequence[AutocompletePart] | Literal["on", "off"] | None = None,
) -> dict:
    validate_length_bounds(min_value, max_value)
    if step is not None and step <= 0:
        raise ValueError("`step` cannot be less than or equal to zero.")

    render_kw: dict = required_render_kw(required_message) if required else {}

    if min_value is not None:
        render_kw["min"] = min_value
        render_kw["data-msg-range-underflow"] = f"Range must be {min_value} or more."

    if max_value is not None:
        render_kw["max"] = max_value
        render_kw["data-msg-range-overflow"] = f"Range must be {max_value} or less."

    if autocomplete is not None:
        render_kw["autocomplete"] = (
            autocomplete
            if isinstance(autocomplete, str)
            else " ".join(map(str, autocomplete))
        )

    render_kw.update({
        "type": "range",
    })

    return render_kw


# ------------------------------------------------------------------------------------------------------
# PHONE VALIDATION
# ------------------------------------------------------------------------------------------------------
PHONE_INVALID = "Please enter a valid phone number."
PHONE_TOO_LONG = f"Please use {PHONE_MAX_LENGTH} characters or fewer."
PHONE_NOT_POSSIBLE = "This phone number has an invalid length."
PHONE_INPUT_PATTERN = (
    r"^\+?[0-9\s().-]+?"
    r"(?:\s*(?:ext\.?|x|#)\s*\d{1,10})?$"
)


def normalize_phone_number(
        value: str | None,
        region: str,
) -> str | None:
    if not value:
        return None

    phone = phonenumbers.parse(
        value,
        region,
    )

    return phonenumbers.format_number(
        phone,
        phonenumbers.PhoneNumberFormat.E164,
    )


def validate_phone_number(form, field) -> None:
    """Validate and normalise phone numbers to E.164."""

    if not field.data:
        return

    country_field = getattr(form, "country_code", None)
    region = country_field.data if country_field is not None else None

    # Without a country selection, require an international number.
    if not region and not field.data.lstrip().startswith("+"):
        raise ValidationError(
            "Please include the international country code, e.g. +44."
        )

    try:
        phone = phonenumbers.parse(field.data, region)

    except NumberParseException as exc:
        raise ValidationError(PHONE_INVALID) from exc

    if not phonenumbers.is_possible_number(phone):
        raise ValidationError(PHONE_NOT_POSSIBLE)

    if not phonenumbers.is_valid_number(phone):
        raise ValidationError(PHONE_INVALID)

    field.data = phonenumbers.format_number(
        phone,
        phonenumbers.PhoneNumberFormat.E164,
    )


def phone_validators(required: bool = False, required_message: str | None = None) -> list:
    validators: list = required_validators(DataRequired, required_message) if required else [Optional()]

    validators.extend([
        Length(
            max=PHONE_MAX_LENGTH,
            message=PHONE_TOO_LONG
        ),
        Regexp(
            PHONE_INPUT_PATTERN,
            message=PHONE_INVALID,
        ),
        validate_phone_number,
    ])

    return validators


def phone_render_kw(required: bool = False, required_message: str | None = None) -> dict:
    render_kw: dict = required_render_kw(required_message) if required else {}
    render_kw.update({
        "type": "tel",
        "pattern": PHONE_INPUT_PATTERN,
        "data-msg-pattern-mismatch": PHONE_INVALID,
        "maxlength": PHONE_MAX_LENGTH,
        "data-msg-too-long": PHONE_TOO_LONG,
        "autocomplete": "tel",
    })

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
        "autocomplete": "email",
    })

    return render_kw


# ------------------------------------------------------------------------------------------------------
# PASSWORD VALIDATION
# ------------------------------------------------------------------------------------------------------
def password_validators(required: bool = False, required_message: str | None = None) -> list:
    return string_validators(PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH, required, required_message)


def password_render_kw(required: bool = False, required_message: str | None = None, existing: bool = False) -> dict:
    render_kw = string_render_kw(PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH, required, required_message)
    render_kw["autocomplete"] = "current-password" if existing else "new-password"
    return render_kw


# ------------------------------------------------------------------------------------------------------
# TIME ZONE VALIDATION
# ------------------------------------------------------------------------------------------------------
TIMEZONE_REQUIRED = "Please select a time zone."
TIMEZONE_INVALID = "Please select a valid time zone."

# Use IANA time zone identifiers as both the stored values and labels.
TIMEZONE_NAMES = frozenset(available_timezones())

TIMEZONE_CHOICES = [
    ("", "Select a time zone"),
    *[
        (name, name)
        for name in sorted(TIMEZONE_NAMES, key=str.casefold)
    ],
]


def validate_timezone(form, field) -> None:
    """Validate that the selected value is a supported IANA time zone."""

    name = field.data

    if not isinstance(name, str) or name not in TIMEZONE_NAMES:
        raise ValidationError(TIMEZONE_INVALID)

    try:
        ZoneInfo(name)

    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValidationError(TIMEZONE_INVALID) from exc


def timezone_validators(required: bool = False) -> list:
    validators: list = (
        required_validators(DataRequired, TIMEZONE_REQUIRED)
        if required
        else [Optional()]
    )

    validators.append(validate_timezone)

    return validators


def timezone_render_kw(required: bool = False) -> dict:
    render_kw: dict = (
        required_render_kw(TIMEZONE_REQUIRED)
        if required
        else {}
    )

    render_kw["data-msg-invalid-choice"] = TIMEZONE_INVALID

    return render_kw


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


def url_validators(
        max_len: int = URL_MAX_LENGTH,
        required: bool = False,
        required_message: str | None = None,
) -> list:
    validators: list = (
        required_validators(DataRequired, required_message)
        if required else [Optional()]
    )

    validators.extend([
        URL(message=URL_INVALID),
        Length(
            max=max_len,
            message=f"Please use {max_len} characters or fewer.",
        ),
    ])

    return validators


def url_render_kw(
        max_len: int = URL_MAX_LENGTH,
        required: bool = False,
        required_message: str | None = None,
) -> dict:
    render_kw = (
        required_render_kw(required_message)
        if required else {}
    )

    render_kw.update({
        "type": "url",
        "maxlength": max_len,
        "data-msg-type-mismatch": URL_INVALID,
        "data-msg-too-long": (
            f"Please use {max_len} characters or fewer."
        ),
        "autocomplete": "url",
    })

    return render_kw


# ------------------------------------------------------------------------------------------------------
# CAFE FORM HELPERS
# ------------------------------------------------------------------------------------------------------

COUNTRY_CHOICES = [
    ("", "Select a country"),
    *[
        (country.alpha_2, country.name)
        for country in sorted(
            pycountry.countries,
            key=lambda country: country.name.casefold(),
        )
    ],
]


# ------------------------------------------------------------------------------------------------------
# OPENING HOURS
# ------------------------------------------------------------------------------------------------------
def validate_opening_time(form, field) -> None:
    if form.is_closed.data:
        return

    if field.data is None:
        raise ValidationError(
            "Enter an opening time or mark this day as closed."
        )


def validate_closing_time(form, field) -> None:
    if form.is_closed.data:
        return

    if field.data is None:
        raise ValidationError(
            "Enter a closing time or mark this day as closed."
        )

    if field.data == form.opens_at.data:
        raise ValidationError(
            "Closing time must differ from opening time."
        )


class OpeningHoursDayForm(Form):
    opens_at = TimeField(
        "Opens",
        format="%H:%M",
        validators=[validate_opening_time],
        render_kw={
            "type": "time",
            "step": 60,
        },
    )

    closes_at = TimeField(
        "Closes",
        format="%H:%M",
        validators=[validate_closing_time],
        render_kw={
            "type": "time",
            "step": 60,
        },
    )

    is_closed = BooleanField("Closed")


# ------------------------------------------------------------------------------------------------------
# FORMS
# ------------------------------------------------------------------------------------------------------

class CafeAddressForm(FlaskForm):
    address = StringField(
        "Find the café's location",
        validators=string_validators(
            min_len=3,
            max_len=300,
            required=True,
        ),
        render_kw=string_render_kw(
            min_len=3,
            max_len=300,
            required=True,
            autocomplete=[
                "street-address"
            ],
        ),
        filters=[strip_string],
    )

    submit = SubmitField("Search")


class CafeForm(FlaskForm):
    name = StringField(
        "Cafe Name",
        validators=string_validators(min_len=2, max_len=50),
        render_kw=string_render_kw(min_len=2, max_len=50),
        filters=[strip_string],
    )

    overview = TextAreaField(
        "Overview",
        validators=string_validators(max_len=20_000),
        render_kw=string_render_kw(max_len=20_000),
        filters=[strip_string],
    )

    phone_number = StringField(
        "Phone Number (Optional)",
        validators=phone_validators(),
        render_kw=phone_render_kw(),
        filters=[strip_string],
    )

    timezone = SelectField(
        "Time Zone",
        choices=TIMEZONE_CHOICES,
        validators=timezone_validators(required=True),
        render_kw=timezone_render_kw(required=True),
        validate_choice=True,
    )

    opening_hours = FieldList(
        FormField(OpeningHoursDayForm),
        min_entries=7,
        max_entries=7,
    )

    # img_url = StringField(
    #     "Thumbnail URL",
    #     validators=url_validators(max_len=500, required=True),
    #     render_kw=url_render_kw(max_len=500, required=True),
    #     filters=[strip_string],
    # )


class CafeAddForm(CafeForm):
    submit = SubmitField("Add Cafe")


class CafeEditForm(CafeForm):
    submit = SubmitField("Save Changes")


# Create a form to submit café reviews
class CafeReviewForm(FlaskForm):
    name = StringField(
        "Name",
        validators=string_validators(
            max_len=50,
            required=True,
            required_message="Please enter your name."
        ),
        render_kw=string_render_kw(
            max_len=50, required=True,
            required_message="Please enter your name.",
            autocomplete=[
                "name"
            ]),
        filters=[strip_string],
    )

    rating = IntegerField(
        "Rating",
        default=5,
        validators=range_validators(
            min_value=1,
            max_value=5,
            required=True,
            required_message="Please rate the café.",
        ),
        render_kw=range_render_kw(
            min_value=1,
            max_value=5,
            step=1,
            required=True,
            required_message="Please rate the café.",
        ),
    )

    body = TextAreaField(
        "Your review",
        validators=string_validators(
            max_len=500,
            required=True,
            required_message="Tell people what it's like."
        ),
        render_kw=string_render_kw(
            max_len=500,
            required=True,
            required_message="Tell people what it's like."
        ),
        filters=[strip_string],
    )

    submit = SubmitField("Post review")
