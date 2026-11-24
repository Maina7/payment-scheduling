from flask import Blueprint

from app.controllers.transaction_controller import (
    generate_qr_code,
    get_transaction,
    get_transactions,
)

transaction_bp = Blueprint("transactions", __name__, url_prefix="/api/qr")

transaction_bp.add_url_rule("/transactions/qrcode", view_func=generate_qr_code, methods=["POST"])
transaction_bp.add_url_rule("/transactions", view_func=get_transactions, methods=["GET"])
transaction_bp.add_url_rule("/transactions/<transaction_id>", view_func=get_transaction, methods=["GET"])
