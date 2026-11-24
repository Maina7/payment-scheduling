from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.db import DatabaseError, get_pool


class TransactionStatus(StrEnum):
    PENDING = "PENDING"
    QR_GENERATED = "QR_GENERATED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


VALID_TRX_CODES = ("BG", "WA", "PB", "SM", "SB")

REQUIRED_COLUMNS = (
    "id", "merchant_name", "ref_no", "amount", "trx_code", "cpi", "size", "status",
    "response_code", "response_description", "request_id", "qr_image_path",
    "error_message", "created_at", "updated_at",
)

CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS transactions (
        id                   SERIAL PRIMARY KEY,
        merchant_name        VARCHAR(255)   NOT NULL,
        ref_no               VARCHAR(100)   NOT NULL,
        amount               NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
        trx_code             VARCHAR(2)     NOT NULL CHECK (trx_code IN ('BG', 'WA', 'PB', 'SM', 'SB')),
        cpi                  VARCHAR(50)    NOT NULL,
        size                 VARCHAR(10)    NOT NULL,
        status               VARCHAR(20)    NOT NULL DEFAULT 'PENDING',
        response_code        VARCHAR(100),
        response_description TEXT,
        request_id           VARCHAR(100),
        qr_image_path        TEXT,
        error_message        TEXT,
        created_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
        updated_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW()
    )
"""

CREATE_INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_transactions_ref_no ON transactions (ref_no)"


def _fetch_one(query, params=None):
    with get_pool().connection() as conn:
        return conn.execute(query, params).fetchone()


def _fetch_all(query, params=None):
    with get_pool().connection() as conn:
        return conn.execute(query, params).fetchall()


def create_transactions_table():
    with get_pool().connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.execute(CREATE_INDEX_SQL)


def verify_transactions_table():
    rows = _fetch_all(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'transactions'
        """
    )
    if not rows:
        raise DatabaseError("Table 'transactions' does not exist")
    existing = {row["column_name"] for row in rows}
    missing = [column for column in REQUIRED_COLUMNS if column not in existing]
    if missing:
        raise DatabaseError(f"Table 'transactions' is missing columns: {', '.join(missing)}")


def init_schema():
    create_transactions_table()
    verify_transactions_table()


def create_transaction(merchant_name, ref_no, amount, trx_code, cpi, size):
    return _fetch_one(
        """
        INSERT INTO transactions (merchant_name, ref_no, amount, trx_code, cpi, size, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (merchant_name, ref_no, amount, trx_code, cpi, size, TransactionStatus.PENDING.value),
    )


def mark_qr_generated(transaction_id, response_code, response_description, request_id, qr_image_path):
    return _fetch_one(
        """
        UPDATE transactions
        SET status = %s, response_code = %s, response_description = %s,
            request_id = %s, qr_image_path = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            TransactionStatus.QR_GENERATED.value,
            response_code,
            response_description,
            request_id,
            qr_image_path,
            transaction_id,
        ),
    )


def mark_failed(transaction_id, error_message, response_code=None, response_description=None):
    return _fetch_one(
        """
        UPDATE transactions
        SET status = %s, error_message = %s, response_code = %s,
            response_description = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            TransactionStatus.FAILED.value,
            error_message,
            response_code,
            response_description,
            transaction_id,
        ),
    )


def update_transaction_status(transaction_id, status):
    try:
        status = TransactionStatus(status)
    except ValueError as exc:
        raise ValueError(f"Invalid transaction status: {status}") from exc
    return _fetch_one(
        "UPDATE transactions SET status = %s, updated_at = NOW() WHERE id = %s RETURNING *",
        (status.value, transaction_id),
    )


def get_transaction_by_id(transaction_id):
    return _fetch_one("SELECT * FROM transactions WHERE id = %s", (transaction_id,))


def get_transactions_by_ref_no(ref_no):
    return _fetch_all(
        "SELECT * FROM transactions WHERE ref_no = %s ORDER BY created_at DESC",
        (ref_no,),
    )


def get_all_transactions(limit=50, offset=0):
    return _fetch_all(
        "SELECT * FROM transactions ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (limit, offset),
    )


def serialize_transaction(row):
    if row is None:
        return None
    result = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result
