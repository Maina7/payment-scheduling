import logging

from flask import Flask
from flask_cors import CORS

from app.config import Config, validate_config
from app.db import check_database_connection, init_pool
from app.errors import register_error_handlers
from app.models.transaction import init_schema
from app.routes.health_routes import health_bp
from app.routes.transaction_routes import transaction_bp
from app.services.mpesa_service import MpesaClient


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def create_app(config_class=Config):
    configure_logging()
    logger = logging.getLogger(__name__)

    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.sort_keys = False
    validate_config(app.config)

    init_pool(
        app.config["DATABASE_URL"],
        min_size=app.config["DB_POOL_MIN_SIZE"],
        max_size=app.config["DB_POOL_MAX_SIZE"],
    )
    init_schema()
    info = check_database_connection()
    logger.info("Connected to database '%s', transactions table verified", info["database"])

    app.extensions["mpesa"] = MpesaClient(
        base_url=app.config["MPESA_BASE_URL"],
        consumer_key=app.config["MPESA_CONSUMER_KEY"],
        consumer_secret=app.config["MPESA_CONSUMER_SECRET"],
        timeout=app.config["MPESA_TIMEOUT"],
    )

    CORS(app)
    register_error_handlers(app)
    app.register_blueprint(health_bp)
    app.register_blueprint(transaction_bp)

    return app
