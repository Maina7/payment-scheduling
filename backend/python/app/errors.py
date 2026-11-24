import logging

from flask import jsonify, request
from werkzeug.exceptions import HTTPException, NotFound

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    @app.errorhandler(NotFound)
    def handle_not_found(error):
        return jsonify(success=False, message=f"Route {request.method} {request.path} not found"), 404

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        return jsonify(success=False, message=error.description), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        logger.exception("Unhandled error")
        return jsonify(success=False, message="Internal server error"), 500
