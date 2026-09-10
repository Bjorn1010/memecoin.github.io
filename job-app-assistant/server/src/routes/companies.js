import { Router } from "express";
import { db } from "../db.js";
import { textToDocxBuffer } from "../services/docx.js";

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
  const { name, url, description, source } = req.body || {};
  if (!name || !name.trim()) {
    return res.status(400).json({ error: "Le nom de l'entreprise est requis" });
  }
  const info = db
    .prepare(
      `INSERT INTO companies (name, url, description, source)
       VALUES (@name, @url, @description, @source)`
    )
    .run({
      name: name.trim(),
      url: url || "",
      description: description || "",
      source: source || "",
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
    "status",
    "cover_letter_text",
    "message_text",
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

companiesRouter.get("/:id/cover-letter.docx", async (req, res) => {
  const company = db.prepare("SELECT * FROM companies WHERE id = ?").get(req.params.id);
  if (!company) return res.status(404).json({ error: "Introuvable" });
  if (!company.cover_letter_text) {
    return res.status(400).json({ error: "Génère d'abord la lettre de motivation." });
  }
  try {
    const buffer = await textToDocxBuffer(company.cover_letter_text, {
      title: `Lettre de motivation - ${company.name}`,
    });
    res.setHeader(
      "Content-Type",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    );
    res.setHeader(
      "Content-Disposition",
      `attachment; filename="Lettre de motivation - ${company.name}.docx"`
    );
    res.send(buffer);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

companiesRouter.delete("/:id", (req, res) => {
  db.prepare("DELETE FROM companies WHERE id = ?").run(req.params.id);
  res.json({ ok: true });
});
