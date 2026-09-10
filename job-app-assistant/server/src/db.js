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

const profileRow = db.prepare("SELECT id FROM profile WHERE id = 1").get();
if (!profileRow) {
  db.prepare("INSERT INTO profile (id) VALUES (1)").run();
}

export function getProfile() {
  return db.prepare("SELECT * FROM profile WHERE id = 1").get();
}

export function updateProfile(fields) {
  const allowed = [
    "full_name",
    "cv_text",
    "cv_docx",
    "cv_filename",
    "cover_letter_text",
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
  const setClause = keys.map((k) => `${k} = @${k}`).join(", ");
  db.prepare(`UPDATE profile SET ${setClause} WHERE id = 1`).run(fields);
  return getProfile();
}
