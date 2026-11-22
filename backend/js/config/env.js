import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

dotenv.config({ path: path.join(__dirname, "..", "..", ".env"), quiet: true });

const REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "MPESA_BASE_URL",
    "MPESA_CONSUMER_KEY",
    "MPESA_CONSUMER_SECRET",
];

export const validateEnv = () => {
    const missing = REQUIRED_ENV_VARS.filter((name) => !process.env[name]?.trim());
    if (missing.length) {
        throw new Error(`Missing required environment variables: ${missing.join(", ")}`);
    }
};
