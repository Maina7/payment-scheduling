import { validateEnv } from "./config/env.js";
import express from "express"
import cors from "cors"
import routes from "./routes/transactionRoutes.js";
import pool, { initDatabase, checkDatabaseConnection } from "./models/transactionModel.js";

const PORT = Number(process.env.PORT) || 5000;

const app = express();
app.use(cors())
app.use(express.json({limit: "1mb"}))

app.get("/api/health", async (req, res) => {
    try {
        const { database } = await checkDatabaseConnection();
        res.json({ success: true, database, status: "connected" });
    } catch (error) {
        res.status(503).json({ success: false, status: "disconnected", message: error.message });
    }
})

app.use("/api/qr", routes)

app.use((req, res) => {
    res.status(404).json({ success: false, message: `Route ${req.method} ${req.originalUrl} not found` });
})

app.use((error, req, res, next) => {
    if (error.type === "entity.parse.failed") {
        return res.status(400).json({ success: false, message: "Invalid JSON body" });
    }
    console.error("Unhandled error", error);
    res.status(500).json({ success: false, message: "Internal server error" });
})

const startServer = async () => {
    try {
        validateEnv();
        const { database } = await initDatabase();
        console.log(`Connected to database '${database}', transactions table verified`);

        const server = app.listen(PORT, () => console.log(`Server running on port ${PORT}`));

        const shutdown = async () => {
            server.close();
            await pool.end();
            process.exit(0);
        };
        process.on("SIGINT", shutdown);
        process.on("SIGTERM", shutdown);
    } catch (error) {
        console.error("Server startup failed:", error.message);
        await pool.end().catch(() => {});
        process.exit(1);
    }
}

startServer();
