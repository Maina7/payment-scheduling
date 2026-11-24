import math

from app.models.transaction import VALID_TRX_CODES

DEFAULT_QR_SIZE = "300"


def _to_positive_number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return int(number) if number.is_integer() else number


def validate_qr_request(body):
    body = body or {}
    errors = []

    merchant_name = body.get("MerchantName")
    ref_no = body.get("RefNo")
    trx_code = body.get("TrxCode")
    cpi = body.get("CPI")
    size = body.get("Size")

    if not isinstance(merchant_name, str) or not merchant_name.strip():
        errors.append("MerchantName is required")
    if not isinstance(ref_no, str) or not ref_no.strip():
        errors.append("RefNo is required")

    amount = _to_positive_number(body.get("Amount"))
    if amount is None:
        errors.append("Amount must be a positive number")

    if trx_code not in VALID_TRX_CODES:
        errors.append(f"TrxCode must be one of {', '.join(VALID_TRX_CODES)}")

    cpi = "" if cpi is None else str(cpi).strip()
    if not cpi:
        errors.append("CPI is required")

    size = DEFAULT_QR_SIZE if size is None else str(size).strip()
    if not size.isdigit() or int(size) <= 0:
        errors.append("Size must be a positive integer (pixels)")

    payload = {
        "MerchantName": merchant_name,
        "RefNo": ref_no,
        "Amount": amount,
        "TrxCode": trx_code,
        "CPI": cpi,
        "Size": size,
    }
    return errors, payload
