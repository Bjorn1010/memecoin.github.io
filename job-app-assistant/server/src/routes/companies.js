import { Router } from "express";
import { db } from "../db.js";

export const companiesRouter = Router();

companiesRouter.get("/", (req, res) => {
  const rows = db
    .prepare("SELECT * FROM companies ORDER BY created_at DESC")
    .all();
  res.json(rows);
});

companiesRouter.get("/:id", (req, res) => {
  const row = db
    .prepare("SELECT * FROM companies WHERE id = ?")
    .get(req.params.id);
  if (!row) return res.status(404).json({ error: "Introuvable" });
  res.json(row);
});

companiesRouter.post("/", (req, res) => {
  const { name, url, description, source, contact_email } = req.body || {};
  if (!name || !name.trim()) {
    return res.status(400).json({ error: "Le nom de l'entreprise est requis" });
  }
  const info = db
    .prepare(
      `INSERT INTO companies (name, url, description, source, contact_email)
       VALUES (@name, @url, @description, @source, @contact_email)`
    )
    .run({
      name: name.trim(),
      url: url || "",
      description: description || "",
      source: source || "",
      contact_email: contact_email || "",
    });
  const row = db.prepare("SELECT * FROM companies WHERE id = ?").get(info.lastInsertRowid);
  res.status(201).json(row);
});

companiesRouter.put("/:id", (req, res) => {
  const existing = db.prepare("SELECT * FROM companies WHERE id = ?").get(req.params.id);
  if (!existing) return res.status(404).json({ error: "Introuvable" });

  const allowed = [
    "name",
    "url",
    "description",
    "source",
    "contact_email",
    "status",
    "cover_letter_text",
    "email_subject",
    "email_body",
  ];
  const fields = {};
  for (const k of allowed) {
    if (req.body[k] !== undefined) fields[k] = req.body[k];
  }
  if (Object.keys(fields).length > 0) {
    const setClause = Object.keys(fields)
      .map((k) => `${k} = @${k}`)
      .join(", ");
    db.prepare(
      `UPDATE companies SET ${setClause}, updated_at = datetime('now') WHERE id = @id`
    ).run({ ...fields, id: req.params.id });
  }
  const row = db.prepare("SELECT * FROM companies WHERE id = ?").get(req.params.id);
  res.json(row);
});

companiesRouter.delete("/:id", (req, res) => {
  db.prepare("DELETE FROM companies WHERE id = ?").run(req.params.id);
  res.json({ ok: true });
});
