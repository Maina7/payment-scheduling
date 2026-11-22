import pg from 'pg';

const { Pool } = pg;

const pool = new Pool(
    process.env.DATABASE_URL ? { connectionString: process.env.DATABASE_URL } : {}
);

pool.on("error", (error) => {
    console.error("Unexpected PostgreSQL client error", error.message);
});

const REQUIRED_COLUMNS = [
    "id", "merchant_name", "ref_no", "amount", "trx_code", "cpi", "size", "status",
    "response_code", "response_description", "request_id", "qr_image_path",
    "error_message", "created_at", "updated_at",
];

export const checkDatabaseConnection = async () => {
    try {
        const { rows } = await pool.query("SELECT current_database() AS database, version() AS version");
        return rows[0];
    } catch (error) {
        throw new Error(`Database connection failed: ${error.message}`);
    }
};

export const verifyTransactionsTable = async () => {
    const { rows } = await pool.query(
        `SELECT column_name FROM information_schema.columns
         WHERE table_schema = current_schema() AND table_name = 'transactions'`
    );
    if (!rows.length) {
        throw new Error("Table 'transactions' does not exist");
    }
    const existing = new Set(rows.map((row) => row.column_name));
    const missing = REQUIRED_COLUMNS.filter((column) => !existing.has(column));
    if (missing.length) {
        throw new Error(`Table 'transactions' is missing columns: ${missing.join(", ")}`);
    }
};

export const initDatabase = async () => {
    const info = await checkDatabaseConnection();
    await createTransactionsTable();
    await verifyTransactionsTable();
    return info;
};

export const TRANSACTION_STATUS = Object.freeze({
    PENDING: 'PENDING',         
    QR_GENERATED: 'QR_GENERATED',
    FAILED: 'FAILED',            
    COMPLETED: 'COMPLETED',     
});

export const createTransactionsTable = async () => {
    await pool.query(`
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
        );
        CREATE INDEX IF NOT EXISTS idx_transactions_ref_no ON transactions (ref_no);
    `);
};

export const createTransaction = async ({ merchantName, refNo, amount, trxCode, cpi, size }) => {
    const { rows } = await pool.query(
        `INSERT INTO transactions (merchant_name, ref_no, amount, trx_code, cpi, size, status)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         RETURNING *`,
        [merchantName, refNo, amount, trxCode, cpi, size, TRANSACTION_STATUS.PENDING]
    );
    return rows[0];
};

export const markQrGenerated = async (id, { responseCode, responseDescription, requestId, qrImagePath }) => {
    const { rows } = await pool.query(
        `UPDATE transactions
         SET status = $2, response_code = $3, response_description = $4,
             request_id = $5, qr_image_path = $6, updated_at = NOW()
         WHERE id = $1
         RETURNING *`,
        [id, TRANSACTION_STATUS.QR_GENERATED, responseCode, responseDescription, requestId ?? null, qrImagePath]
    );
    return rows[0];
};

export const markFailed = async (id, { errorMessage, responseCode = null, responseDescription = null }) => {
    const { rows } = await pool.query(
        `UPDATE transactions
         SET status = $2, error_message = $3, response_code = $4,
             response_description = $5, updated_at = NOW()
         WHERE id = $1
         RETURNING *`,
        [id, TRANSACTION_STATUS.FAILED, errorMessage, responseCode, responseDescription]
    );
    return rows[0];
};

export const updateTransactionStatus = async (id, status) => {
    if (!Object.values(TRANSACTION_STATUS).includes(status)) {
        throw new Error(`Invalid transaction status: ${status}`);
    }
    const { rows } = await pool.query(
        `UPDATE transactions SET status = $2, updated_at = NOW() WHERE id = $1 RETURNING *`,
        [id, status]
    );
    return rows[0];
};

export const getTransactionById = async (id) => {
    const { rows } = await pool.query(`SELECT * FROM transactions WHERE id = $1`, [id]);
    return rows[0] ?? null;
};

export const getTransactionsByRefNo = async (refNo) => {
    const { rows } = await pool.query(
        `SELECT * FROM transactions WHERE ref_no = $1 ORDER BY created_at DESC`,
        [refNo]
    );
    return rows;
};

export const getAllTransactions = async ({ limit = 50, offset = 0 } = {}) => {
    const { rows } = await pool.query(
        `SELECT * FROM transactions ORDER BY created_at DESC LIMIT $1 OFFSET $2`,
        [limit, offset]
    );
    return rows;
};

export default pool;
