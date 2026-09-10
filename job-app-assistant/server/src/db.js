import { createClient } from "@libsql/client";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * En production, pointe vers une base Turso distante (persistante, gratuite)
 * via TURSO_DATABASE_URL/TURSO_AUTH_TOKEN. En local, sans ces variables,
 * retombe sur un fichier SQLite local (pratique pour développer hors ligne).
 */
export const db = process.env.TURSO_DATABASE_URL
  ? createClient({
      url: process.env.TURSO_DATABASE_URL,
      authToken: process.env.TURSO_AUTH_TOKEN,
    })
  : createClient({
      url: `file:${(() => {
        const dataDir = path.join(__dirname, "..", "data");
        fs.mkdirSync(dataDir, { recursive: true });
        return path.join(dataDir, "app.db");
      })()}`,
    });

await db.executeMultiple(`
  CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    full_name TEXT DEFAULT '',
    cv_text TEXT DEFAULT '',
    cv_docx BLOB,
    cv_filename TEXT DEFAULT '',
    cv_font_family TEXT DEFAULT '',
    cv_font_size INTEGER,
    cover_letter_text TEXT DEFAULT '',
    cover_letter_font_family TEXT DEFAULT '',
    cover_letter_font_size INTEGER,
    bulletin1_file BLOB,
    bulletin1_filename TEXT DEFAULT '',
    bulletin1_mimetype TEXT DEFAULT '',
    bulletin2_file BLOB,
    bulletin2_filename TEXT DEFAULT '',
    bulletin2_mimetype TEXT DEFAULT '',
    bulletin3_file BLOB,
    bulletin3_filename TEXT DEFAULT '',
    bulletin3_mimetype TEXT DEFAULT ''
  );

  CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT DEFAULT '',
    description TEXT DEFAULT '',
    source TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    cover_letter_text TEXT DEFAULT '',
    cv_modified_text TEXT DEFAULT '',
    cv_change_summary TEXT DEFAULT '',
    message_text TEXT DEFAULT '',
    fetched_context TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
  );
`);

const { rows: profileRows } = await db.execute("SELECT id FROM profile WHERE id = 1");
if (profileRows.length === 0) {
  await db.execute("INSERT INTO profile (id) VALUES (1)");
}

/** Convertit une colonne BLOB renvoyée par libsql (ArrayBuffer/Uint8Array) en Buffer Node. */
export function toBuffer(value) {
  return value == null ? null : Buffer.from(value);
}

export async function getProfile() {
  const { rows } = await db.execute("SELECT * FROM profile WHERE id = 1");
  return rows[0];
}

export async function updateProfile(fields) {
  const allowed = [
    "full_name",
    "cv_text",
    "cv_docx",
    "cv_filename",
    "cv_font_family",
    "cv_font_size",
    "cover_letter_text",
    "cover_letter_font_family",
    "cover_letter_font_size",
    "bulletin1_file",
    "bulletin1_filename",
    "bulletin1_mimetype",
    "bulletin2_file",
    "bulletin2_filename",
    "bulletin2_mimetype",
    "bulletin3_file",
    "bulletin3_filename",
    "bulletin3_mimetype",
  ];
  const keys = Object.keys(fields).filter((k) => allowed.includes(k));
  if (keys.length === 0) return getProfile();
  const setClause = keys.map((k) => `${k} = ?`).join(", ");
  const args = keys.map((k) => fields[k]);
  await db.execute({ sql: `UPDATE profile SET ${setClause} WHERE id = 1`, args });
  return getProfile();
}
