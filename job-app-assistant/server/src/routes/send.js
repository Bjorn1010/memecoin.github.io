import { Router } from "express";
import { db, getProfile } from "../db.js";
import { textToDocxBuffer } from "../services/docx.js";
import { sendApplicationEmail } from "../services/mailer.js";

export const sendRouter = Router();

async function sendForCompany(company, profile) {
  if (!company.cover_letter_text) {
    throw new Error("Génère d'abord la lettre de motivation pour cette entreprise.");
  }

  const attachments = [];

  if (profile.cv_docx) {
    attachments.push({
      filename: profile.cv_filename || "CV.docx",
      content: profile.cv_docx,
    });
  }

  const coverLetterBuffer = await textToDocxBuffer(company.cover_letter_text, {
    title: `Lettre de motivation - ${company.name}`,
  });
  attachments.push({
    filename: `Lettre de motivation - ${company.name}.docx`,
    content: coverLetterBuffer,
  });

  await sendApplicationEmail({
    profile,
    to: company.contact_email,
    subject: company.email_subject || `Candidature - ${company.name}`,
    body: company.email_body || company.cover_letter_text,
    attachments,
  });

  db.prepare(
    `UPDATE companies SET status = 'sent', sent_at = datetime('now'), updated_at = datetime('now') WHERE id = ?`
  ).run(company.id);

  return db.prepare("SELECT * FROM companies WHERE id = ?").get(company.id);
}

sendRouter.post("/:id", async (req, res) => {
  const company = db.prepare("SELECT * FROM companies WHERE id = ?").get(req.params.id);
  if (!company) return res.status(404).json({ error: "Introuvable" });
  try {
    const profile = getProfile();
    const updated = await sendForCompany(company, profile);
    res.json(updated);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Envoie à toutes les entreprises prêtes (générées, avec email de contact, pas encore envoyées).
sendRouter.post("/", async (req, res) => {
  const profile = getProfile();
  const ready = db
    .prepare(
      `SELECT * FROM companies WHERE status = 'generated' AND contact_email != '' ORDER BY created_at ASC`
    )
    .all();

  const results = [];
  for (const company of ready) {
    try {
      await sendForCompany(company, profile);
      results.push({ id: company.id, name: company.name, ok: true });
    } catch (err) {
      results.push({ id: company.id, name: company.name, ok: false, error: err.message });
    }
  }
  res.json({ processed: results.length, results });
});
