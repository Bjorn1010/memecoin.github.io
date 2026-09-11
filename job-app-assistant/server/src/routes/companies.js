import { Router } from "express";
import { db, getProfile, toBuffer } from "../db.js";
import { textToDocxBuffer, fillDocxTemplate } from "../services/docx.js";
import { docxBufferToPdf } from "../services/pdf.js";

export const companiesRouter = Router();

async function getCompany(id, userId) {
  const { rows } = await db.execute({
    sql: "SELECT * FROM companies WHERE id = ? AND user_id = ?",
    args: [id, userId],
  });
  return rows[0];
}

companiesRouter.get("/", async (req, res) => {
  const { rows } = await db.execute({
    sql: "SELECT * FROM companies WHERE user_id = ? ORDER BY created_at DESC",
    args: [req.session.userId],
  });
  res.json(rows);
});

companiesRouter.get("/:id", async (req, res) => {
  const row = await getCompany(req.params.id, req.session.userId);
  if (!row) return res.status(404).json({ error: "Introuvable" });
  res.json(row);
});

companiesRouter.post("/", async (req, res) => {
  const { name, url, address, description, source } = req.body || {};
  if (!name || !name.trim()) {
    return res.status(400).json({ error: "Le nom de l'entreprise est requis" });
  }
  const info = await db.execute({
    sql: `INSERT INTO companies (user_id, name, url, address, description, source) VALUES (?, ?, ?, ?, ?, ?)`,
    args: [req.session.userId, name.trim(), url || "", address || "", description || "", source || ""],
  });
  const row = await getCompany(Number(info.lastInsertRowid), req.session.userId);
  res.status(201).json(row);
});

companiesRouter.put("/:id", async (req, res) => {
  const existing = await getCompany(req.params.id, req.session.userId);
  if (!existing) return res.status(404).json({ error: "Introuvable" });

  const allowed = [
    "name",
    "url",
    "address",
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
      .map((k) => `${k} = ?`)
      .join(", ");
    const args = [...Object.values(fields), req.params.id, req.session.userId];
    await db.execute({
      sql: `UPDATE companies SET ${setClause}, updated_at = datetime('now') WHERE id = ? AND user_id = ?`,
      args,
    });
  }
  const row = await getCompany(req.params.id, req.session.userId);
  res.json(row);
});

async function buildCoverLetterDocx(company, profile) {
  if (profile.cover_letter_docx && company.cover_letter_replacements) {
    // Remplacement chirurgical dans le fichier .docx original : préserve
    // à 100% la mise en page, la police et le style de la lettre de base.
    const replacements = JSON.parse(company.cover_letter_replacements);
    return fillDocxTemplate(toBuffer(profile.cover_letter_docx), replacements);
  }
  return textToDocxBuffer(company.cover_letter_text, {
    title: `Lettre de motivation - ${company.name}`,
    fontFamily: profile.cover_letter_font_family || profile.cv_font_family,
    fontSize: profile.cover_letter_font_size || profile.cv_font_size,
  });
}

function buildCvModifieDocx(company, profile) {
  return textToDocxBuffer(company.cv_modified_text, {
    title: `CV - ${company.name}`,
    fontFamily: profile.cv_font_family,
    fontSize: profile.cv_font_size,
  });
}

function sendDocx(res, buffer, filename) {
  res.setHeader(
    "Content-Type",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  );
  res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
  res.send(buffer);
}

async function sendPdf(res, docxBuffer, filename) {
  const pdf = await docxBufferToPdf(docxBuffer);
  res.setHeader("Content-Type", "application/pdf");
  res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
  res.send(pdf);
}

companiesRouter.get("/:id/cover-letter.:ext(docx|pdf)", async (req, res) => {
  const company = await getCompany(req.params.id, req.session.userId);
  if (!company) return res.status(404).json({ error: "Introuvable" });
  if (!company.cover_letter_text) {
    return res.status(400).json({ error: "Génère d'abord la lettre de motivation." });
  }
  try {
    const profile = await getProfile(req.session.userId);
    const buffer = await buildCoverLetterDocx(company, profile);
    const filename = `Lettre de motivation - ${company.name}.${req.params.ext}`;
    if (req.params.ext === "pdf") {
      await sendPdf(res, buffer, filename);
    } else {
      sendDocx(res, buffer, filename);
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

companiesRouter.get("/:id/cv-modifie.:ext(docx|pdf)", async (req, res) => {
  const company = await getCompany(req.params.id, req.session.userId);
  if (!company) return res.status(404).json({ error: "Introuvable" });
  if (!company.cv_modified_text) {
    return res.status(404).json({ error: "Aucun CV modifié pour cette entreprise." });
  }
  try {
    const profile = await getProfile(req.session.userId);
    const buffer = await buildCvModifieDocx(company, profile);
    const filename = `CV modifie - ${company.name}.${req.params.ext}`;
    if (req.params.ext === "pdf") {
      await sendPdf(res, buffer, filename);
    } else {
      sendDocx(res, buffer, filename);
    }
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

companiesRouter.delete("/:id", async (req, res) => {
  await db.execute({
    sql: "DELETE FROM companies WHERE id = ? AND user_id = ?",
    args: [req.params.id, req.session.userId],
  });
  res.json({ ok: true });
});
