import "dotenv/config";
import express from "express";
import cookieSession from "cookie-session";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

import { authRouter } from "./routes/auth.js";
import { profileRouter } from "./routes/profile.js";
import { companiesRouter } from "./routes/companies.js";
import { generateRouter } from "./routes/generate.js";
import { requireAuth } from "./auth.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();

app.use(express.json({ limit: "15mb" }));
app.use(
  cookieSession({
    name: "session",
    secret: process.env.SESSION_SECRET || "dev-secret-change-me",
    maxAge: 30 * 24 * 60 * 60 * 1000,
    sameSite: "lax",
  })
);

app.use("/api/auth", authRouter);
app.use("/api/profile", requireAuth, profileRouter);
app.use("/api/companies", requireAuth, companiesRouter);
app.use("/api/generate", requireAuth, generateRouter);

// Sert le frontend React buildé (npm run build dans web/), s'il existe.
const webDist = path.join(__dirname, "..", "..", "web", "dist");
if (fs.existsSync(webDist)) {
  app.use(express.static(webDist));
  app.get(/^(?!\/api).*/, (req, res) => {
    res.sendFile(path.join(webDist, "index.html"));
  });
}

const port = process.env.PORT || 8787;
app.listen(port, () => {
  console.log(`Job App Assistant en écoute sur http://localhost:${port}`);
});
