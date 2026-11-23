import os

import cloudinary
from dotenv import load_dotenv
from flask import Flask
from flask_bootstrap import Bootstrap

from web.extensions import db, migrate, limiter


# --------------------------------------------------
# Environment validation
# --------------------------------------------------

def get_required_env(name: str) -> str:
    """Get a required environment variable."""

    value = os.environ.get(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is not configured."
        )

    return value


def get_optional_env(
        name: str,
        default: str | None = None,
) -> str | None:
    """Get an optional environment variable."""

    value = os.environ.get(name, "").strip()

    return value or default


def get_env_group(
        *names: str,
        required: bool = False,
) -> dict[str, str | None]:
    """
    Validate a group of related environment variables.

    If any variable is configured, all must be configured.
    If required=True, all must be configured.
    """

    values = {
        name: get_optional_env(name)
        for name in names
    }

    configured = [
        bool(value)
        for value in values.values()
    ]

    if required and not all(configured):
        missing = [
            name
            for name, value in values.items()
            if not value
        ]

        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )

    if any(configured) and not all(configured):
        missing = [
            name
            for name, value in values.items()
            if not value
        ]

        raise RuntimeError(
            "Incomplete environment configuration. "
            "The following variables are missing: "
            + ", ".join(missing)
        )

    return values


def get_env_bool(
        name: str,
        default: bool = False,
) -> bool:
    """Parse an environment variable as a boolean."""

    value = get_optional_env(name)

    if value is None:
        return default

    value = value.lower()

    if value in {"1", "true", "yes", "on"}:
        return True

    if value in {"0", "false", "no", "off"}:
        return False

    raise RuntimeError(
        f"Environment variable '{name}' must be a boolean."
    )


# --------------------------------------------------
# Application factory
# --------------------------------------------------

def create_app() -> Flask:
    load_dotenv()
    env = os.environ

    app = Flask(__name__)

    # --------------------------------------------------
    # Application configuration
    # --------------------------------------------------

    app.config.update({

        "SECRET_KEY": get_required_env("FLASK_KEY"),

        "DEBUG": get_env_bool("FLASK_DEBUG"),

        "SQLALCHEMY_DATABASE_URI": get_required_env(
            "DATABASE_URI"
        ),

        "RATELIMIT_STORAGE_URI": get_optional_env(
            "STORAGE_URI",
            "memory://"
        ),

        "TOMTOM_API_KEY": get_required_env(
            "TOMTOM_API_KEY"
        ),

        "MAX_CONTENT_LENGTH": 106 * 1024 * 1024,

    })

    # --------------------------------------------------
    # Cloudinary configuration
    # --------------------------------------------------

    cloudinary_configs = get_env_group(
        "CLOUDINARY_NAME",
        "CLOUDINARY_KEY",
        "CLOUDINARY_SECRET",
    )

    app.config.update({

        "CLOUDINARY_NAME": cloudinary_configs["CLOUDINARY_NAME"],

        "CLOUDINARY_KEY": cloudinary_configs["CLOUDINARY_KEY"],

        "CLOUDINARY_SECRET": cloudinary_configs["CLOUDINARY_SECRET"],

        "CLOUDINARY_ENABLED": bool(
            cloudinary_configs["CLOUDINARY_NAME"]
        ),

    })

    if app.config["CLOUDINARY_ENABLED"]:
        cloudinary.config(
            cloud_name=app.config["CLOUDINARY_NAME"],
            api_key=app.config["CLOUDINARY_KEY"],
            api_secret=app.config["CLOUDINARY_SECRET"],
            secure=True,
        )

    # --------------------------------------------------
    # Extensions
    # --------------------------------------------------

    Bootstrap(app)

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # --------------------------------------------------
    # Register models
    # --------------------------------------------------

    from web.models import Cafe, CafeAttribute

    # --------------------------------------------------
    # Register blueprints
    # --------------------------------------------------

    from web.routes.listing import listing
    from web.routes.main import main
    app.register_blueprint(listing)
    app.register_blueprint(main)

    return app
