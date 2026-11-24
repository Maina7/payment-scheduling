import logging

import psycopg
from flask import current_app, jsonify, request

from app.models import transaction as transaction_model
from app.services.mpesa_service import MpesaError
from app.services.qr_service import save_qr_code_as_png
from app.utils.validators import validate_qr_request

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def _safe_mark_failed(transaction_id, error_message, response_code=None, response_description=None):
    try:
        transaction_model.mark_failed(transaction_id, error_message, response_code, response_description)
    except psycopg.Error as exc:
        logger.error("Failed to mark transaction %s as failed: %s", transaction_id, exc)


def generate_qr_code():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(success=False, message="Request body must be a JSON object"), 400

    errors, payload = validate_qr_request(body)
    if errors:
        return jsonify(success=False, errors=errors), 400

    try:
        transaction = transaction_model.create_transaction(
            merchant_name=payload["MerchantName"],
            ref_no=payload["RefNo"],
            amount=payload["Amount"],
            trx_code=payload["TrxCode"],
            cpi=payload["CPI"],
            size=payload["Size"],
        )
    except psycopg.Error as exc:
        logger.error("Failed to record transaction: %s", exc)
        return jsonify(success=False, message="Could not record transaction"), 500

    transaction_id = transaction["id"]
    mpesa = current_app.extensions["mpesa"]

    try:
        data = mpesa.generate_qr_code(payload)
    except MpesaError as exc:
        logger.error("Failed to generate MPESA QR code: %s", exc.message)
        _safe_mark_failed(transaction_id, exc.message, exc.error_code, exc.response_description)
        return jsonify(success=False, message=exc.message, transactionId=transaction_id), exc.status_code

    qr_code = data.get("QRCode")
    if not qr_code:
        _safe_mark_failed(
            transaction_id,
            "No QRCode in Safaricom response",
            data.get("ResponseCode"),
            data.get("ResponseDescription"),
        )
        return jsonify(
            success=False,
            message=data.get("ResponseDescription") or "QR code was not generated",
            transactionId=transaction_id,
        ), 502

    try:
        qr_image_path = save_qr_code_as_png(qr_code, transaction_id, current_app.config["QR_CODE_DIR"])
        updated = transaction_model.mark_qr_generated(
            transaction_id,
            response_code=data.get("ResponseCode"),
            response_description=data.get("ResponseDescription"),
            request_id=data.get("RequestID"),
            qr_image_path=qr_image_path,
        )
    except (ValueError, OSError, psycopg.Error) as exc:
        logger.error("Failed to store QR code for transaction %s: %s", transaction_id, exc)
        _safe_mark_failed(transaction_id, str(exc))
        return jsonify(success=False, message="Could not store QR code", transactionId=transaction_id), 500

    logger.info("QR code generated for transaction %s", transaction_id)
    return jsonify(
        success=True,
        message=data.get("ResponseDescription"),
        transaction=transaction_model.serialize_transaction(updated),
        qrCode=f"data:image/png;base64,{qr_code}",
    ), 201


def get_transaction(transaction_id):
    if not transaction_id.isdigit() or int(transaction_id) <= 0:
        return jsonify(success=False, message="Invalid transaction id"), 400
    try:
        transaction = transaction_model.get_transaction_by_id(int(transaction_id))
    except psycopg.Error as exc:
        logger.error("Failed to fetch transaction: %s", exc)
        return jsonify(success=False, message="Could not fetch transaction"), 500
    if transaction is None:
        return jsonify(success=False, message="Transaction not found"), 404
    return jsonify(success=True, transaction=transaction_model.serialize_transaction(transaction))


def get_transactions():
    limit = request.args.get("limit", default=DEFAULT_LIMIT, type=int)
    offset = request.args.get("offset", default=0, type=int)
    limit = min(max(limit or DEFAULT_LIMIT, 1), MAX_LIMIT)
    offset = max(offset or 0, 0)
    try:
        rows = transaction_model.get_all_transactions(limit=limit, offset=offset)
    except psycopg.Error as exc:
        logger.error("Failed to fetch transactions: %s", exc)
        return jsonify(success=False, message="Could not fetch transactions"), 500
    return jsonify(success=True, transactions=[transaction_model.serialize_transaction(row) for row in rows])
