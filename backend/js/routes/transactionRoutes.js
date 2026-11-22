import { Router } from "express";
import { generateQRCode, getTransaction, getTransactions } from "../controllers/transactionControllers.js";

const routes = Router()

routes.post("/transactions/qrcode", generateQRCode)
routes.get("/transactions", getTransactions)
routes.get("/transactions/:id", getTransaction)

export default routes;
