import Database from "better-sqlite3";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(__dirname, "..", "data");
fs.mkdirSync(dataDir, { recursive: true });

export const db = new Database(path.join(dataDir, "app.db"));
db.pragma("journal_mode = WAL");

db.exec(`
  CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    full_name TEXT DEFAULT '',
    cv_text TEXT DEFAULT '',
    cv_docx BLOB,
    cv_filename TEXT DEFAULT '',
    cover_letter_text TEXT DEFAULT '',
    smtp_host TEXT DEFAULT '',
    smtp_port INTEGER DEFAULT 587,
    smtp_secure INTEGER DEFAULT 0,
    smtp_user TEXT DEFAULT '',
    smtp_pass TEXT DEFAULT '',
    smtp_from_name TEXT DEFAULT '',
    smtp_from_email TEXT DEFAULT ''
  );

  CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT DEFAULT '',
    description TEXT DEFAULT '',
    source TEXT DEFAULT '',
    contact_email TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    cover_letter_text TEXT DEFAULT '',
    cv_suggestions TEXT DEFAULT '',
    cv_changes_applied INTEGER DEFAULT 0,
    email_subject TEXT DEFAULT '',
    email_body TEXT DEFAULT '',
    fetched_context TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    sent_at TEXT
  );
`);

const profileRow = db.prepare("SELECT id FROM profile WHERE id = 1").get();
if (!profileRow) {
  db.prepare("INSERT INTO profile (id) VALUES (1)").run();
}

export function getProfile() {
  return db.prepare("SELECT * FROM profile WHERE id = 1").get();
}

/**
 * Profil avec les identifiants SMTP éventuellement surchargés par des variables
 * d'environnement (SMTP_HOST, SMTP_PORT, SMTP_SECURE, SMTP_USER, SMTP_PASS,
 * SMTP_FROM_NAME, SMTP_FROM_EMAIL). Permet de configurer l'envoi d'email une
 * seule fois côté hébergeur, sans jamais taper le mot de passe dans l'appli.
 */
export function getEffectiveProfile() {
  const p = getProfile();
  return {
    ...p,
    smtp_host: process.env.SMTP_HOST || p.smtp_host,
    smtp_port: Number(process.env.SMTP_PORT) || p.smtp_port || 587,
    smtp_secure:
      process.env.SMTP_SECURE !== undefined
        ? process.env.SMTP_SECURE === "true"
        : !!p.smtp_secure,
    smtp_user: process.env.SMTP_USER || p.smtp_user,
    smtp_pass: process.env.SMTP_PASS || p.smtp_pass,
    smtp_from_name: process.env.SMTP_FROM_NAME || p.smtp_from_name,
    smtp_from_email: process.env.SMTP_FROM_EMAIL || p.smtp_from_email,
  };
}

export function updateProfile(fields) {
  const allowed = [
    "full_name",
    "cv_text",
    "cv_docx",
    "cv_filename",
    "cover_letter_text",
    "smtp_host",
    "smtp_port",
    "smtp_secure",
    "smtp_user",
    "smtp_pass",
    "smtp_from_name",
    "smtp_from_email",
  ];
  const keys = Object.keys(fields).filter((k) => allowed.includes(k));
  if (keys.length === 0) return getProfile();
  const setClause = keys.map((k) => `${k} = @${k}`).join(", ");
  db.prepare(`UPDATE profile SET ${setClause} WHERE id = 1`).run(fields);
  return getProfile();
}
