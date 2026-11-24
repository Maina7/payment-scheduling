from flask import Blueprint, jsonify

from app.db import DatabaseError, check_database_connection

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.get("/health")
def health():
    try:
        info = check_database_connection()
    except DatabaseError as exc:
        return jsonify(success=False, status="disconnected", message=str(exc)), 503
    return jsonify(success=True, status="connected", database=info["database"])
