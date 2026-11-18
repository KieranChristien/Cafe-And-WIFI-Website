import phonenumbers

from phonenumbers import (
    NumberParseException,
    PhoneNumberFormat,
)


def format_phone_number(value: str | None) -> str:
    """Format an E.164 phone number for international display."""

    if not value:
        return ""

    try:
        phone = phonenumbers.parse(value, None)

        if not phonenumbers.is_valid_number(phone):
            return value

        return phonenumbers.format_number(
            phone,
            PhoneNumberFormat.INTERNATIONAL,
        )

    except NumberParseException:
        return value