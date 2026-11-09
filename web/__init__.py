import os
from dotenv import load_dotenv
from flask import Flask
from flask_bootstrap import Bootstrap4

from web.extensions import db, migrate, limiter


def create_app() -> Flask:
    load_dotenv()
    env = os.environ

    app = Flask(__name__)

    # Configuration
    secret_key = env.get("FLASK_KEY")

    if not secret_key:
        raise RuntimeError("SECRET_KEY is not configured")

    app.config['SECRET_KEY'] = secret_key

    # Debug configuration
    app.config["DEBUG"] = env.get(
        "FLASK_DEBUG", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}

    database_url = env.get('DATABASE_URI')
    if not database_url:
        raise RuntimeError("DATABASE_URI is not configured")

    app.config['RATELIMIT_STORAGE_URI'] = env.get(
        "STORAGE_URI",
        "memory://"
    )

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url

    # Extensions
    Bootstrap4(app)
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Import models so SQLAlchemy registers them with metadata
    from web.models import Cafe, CafeAttribute

    # Register blueprints
    from web.routes.listing import listing
    from web.routes.main import main
    app.register_blueprint(listing)
    app.register_blueprint(main)

    return app
