import axios from 'axios'
import fs from 'fs/promises'
import path from 'path'
import { fileURLToPath } from 'url'
import {
    createTransaction,
    markQrGenerated,
    markFailed,
    getTransactionById,
    getAllTransactions,
} from '../models/transactionModel.js'

let cachedToken = null;
let tokenExpiry = null

const getMpesaBaseUrl = () => process.env.MPESA_BASE_URL

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const QR_CODE_DIR = process.env.QR_CODE_DIR || path.join(__dirname, '..', 'qrcodes');

const VALID_TRX_CODES = ['BG', 'WA', 'PB', 'SM', 'SB'];

export const getAccessToken = async() => {
    if(cachedToken && tokenExpiry && Date.now() < tokenExpiry-60000){
        return cachedToken;
    }

    const consumerKey = process.env.MPESA_CONSUMER_KEY;
    const consumerSecret = process.env.MPESA_CONSUMER_SECRET;
    const auth = Buffer.from(`${consumerKey}:${consumerSecret}`).toString("base64");
    const baseUrl = getMpesaBaseUrl();

    try{
        const response = await axios.get(
            `${baseUrl}/oauth/v1/generate?grant_type=client_credentials`,
            {headers: {Authorization: `Basic ${auth}`}}
        );
        cachedToken = response.data.access_token;
        tokenExpiry = Date.now() + response.data.expires_in * 1000;
        console.log("MPESA Token generated successfully");
        return cachedToken;
    }catch(error){
        console.error("Failed to generate MPESA access token", error.message);
        throw new Error("MPESA Authentication failed")

    }
}

const clearCachedToken = () => {
    cachedToken = null;
    tokenExpiry = null;
}

const validateQrRequest = (body = {}) => {
    const { MerchantName, RefNo, Amount, TrxCode, CPI, Size } = body;
    const errors = [];

    if (!MerchantName || typeof MerchantName !== 'string') errors.push('MerchantName is required');
    if (!RefNo || typeof RefNo !== 'string') errors.push('RefNo is required');

    const amount = Number(Amount);
    if (!Number.isFinite(amount) || amount <= 0) errors.push('Amount must be a positive number');

    if (!VALID_TRX_CODES.includes(TrxCode)) {
        errors.push(`TrxCode must be one of ${VALID_TRX_CODES.join(', ')}`);
    }

    if (CPI === undefined || CPI === null || String(CPI).trim() === '') errors.push('CPI is required');

    const size = Size === undefined ? '300' : String(Size);
    if (!/^\d+$/.test(size) || Number(size) <= 0) errors.push('Size must be a positive integer (pixels)');

    return {
        errors,
        payload: {
            MerchantName,
            RefNo,
            Amount: amount,
            TrxCode,
            CPI: String(CPI ?? '').trim(),
            Size: size,
        },
    };
}

const requestQrCode = async (payload, retry = true) => {
    const token = await getAccessToken();
    try {
        const response = await axios.post(
            `${getMpesaBaseUrl()}/mpesa/qrcode/v1/generate`,
            payload,
            { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } }
        );
        return response.data;
    } catch (error) {
        if (retry && error.response?.status === 401) {
            clearCachedToken();
            return requestQrCode(payload, false);
        }
        throw error;
    }
}

const saveQrCodeAsPng = async (base64String, transactionId) => {
    const cleaned = base64String.replace(/^data:image\/\w+;base64,/, '');
    const buffer = Buffer.from(cleaned, 'base64');

    await fs.mkdir(QR_CODE_DIR, { recursive: true });
    const filePath = path.join(QR_CODE_DIR, `qr_${transactionId}_${Date.now()}.png`);
    await fs.writeFile(filePath, buffer);
    return filePath;
}

export const generateQRCode = async (req, res) => {
    const { errors, payload } = validateQrRequest(req.body);
    if (errors.length) {
        return res.status(400).json({ success: false, errors });
    }

    let transaction;
    try {
        transaction = await createTransaction({
            merchantName: payload.MerchantName,
            refNo: payload.RefNo,
            amount: payload.Amount,
            trxCode: payload.TrxCode,
            cpi: payload.CPI,
            size: payload.Size,
        });
    } catch (error) {
        console.error("Failed to record transaction", error.message);
        return res.status(500).json({ success: false, message: "Could not record transaction" });
    }

    try {
        const data = await requestQrCode(payload);

        if (!data?.QRCode) {
            await markFailed(transaction.id, {
                errorMessage: "No QRCode in Safaricom response",
                responseCode: data?.ResponseCode,
                responseDescription: data?.ResponseDescription,
            });
            return res.status(502).json({
                success: false,
                message: data?.ResponseDescription || "QR code was not generated",
                transactionId: transaction.id,
            });
        }

        const qrImagePath = await saveQrCodeAsPng(data.QRCode, transaction.id);

        const updated = await markQrGenerated(transaction.id, {
            responseCode: data.ResponseCode,
            responseDescription: data.ResponseDescription,
            requestId: data.RequestID,
            qrImagePath,
        });

        console.log(`QR code generated for transaction ${transaction.id}`);
        return res.status(201).json({
            success: true,
            message: data.ResponseDescription,
            transaction: updated,
            qrCode: `data:image/png;base64,${data.QRCode}`,
        });
    } catch (error) {
        const mpesaError = error.response?.data;
        const errorMessage = mpesaError?.errorMessage || mpesaError?.ResponseDescription || error.message;
        console.error("Failed to generate MPESA QR code", errorMessage);

        await markFailed(transaction.id, {
            errorMessage,
            responseCode: mpesaError?.errorCode || mpesaError?.ResponseCode,
            responseDescription: mpesaError?.ResponseDescription,
        }).catch((dbError) => console.error("Failed to mark transaction as failed", dbError.message));

        return res.status(error.response?.status || 500).json({
            success: false,
            message: errorMessage,
            transactionId: transaction.id,
        });
    }
}

export const getTransaction = async (req, res) => {
    const id = Number(req.params.id);
    if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({ success: false, message: "Invalid transaction id" });
    }
    try {
        const transaction = await getTransactionById(id);
        if (!transaction) {
            return res.status(404).json({ success: false, message: "Transaction not found" });
        }
        return res.json({ success: true, transaction });
    } catch (error) {
        console.error("Failed to fetch transaction", error.message);
        return res.status(500).json({ success: false, message: "Could not fetch transaction" });
    }
}

export const getTransactions = async (req, res) => {
    const limit = Math.min(Math.max(parseInt(req.query.limit, 10) || 50, 1), 100);
    const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);
    try {
        const transactions = await getAllTransactions({ limit, offset });
        return res.json({ success: true, transactions });
    } catch (error) {
        console.error("Failed to fetch transactions", error.message);
        return res.status(500).json({ success: false, message: "Could not fetch transactions" });
    }
}
