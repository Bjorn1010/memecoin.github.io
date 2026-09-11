import { Router } from "express";
import { db, getProfile } from "../db.js";
import { fetchCompanyContext } from "../services/fetchCompany.js";
import { generateApplication } from "../services/ai.js";

export const generateRouter = Router();

async function getCompany(id, userId) {
  const { rows } = await db.execute({
    sql: "SELECT * FROM companies WHERE id = ? AND user_id = ?",
    args: [id, userId],
  });
  return rows[0];
}

async function generateForCompany(company, profile) {
  const fetchedContext = company.url
    ? await fetchCompanyContext(company.url)
    : "";

  const result = await generateApplication({
    fullName: profile.full_name,
    cvText: profile.cv_text,
    baseCoverLetter: profile.cover_letter_text,
    companyName: company.name,
    companyAddress: company.address,
    companyDescription: company.description,
    fetchedContext,
    source: company.source,
  });

  // Ne remplace l'adresse que si elle n'a pas déjà été renseignée (on ne veut
  // jamais écraser une correction manuelle avec une extraction automatique).
  const address = company.address || result.foundAddress || "";

  await db.execute({
    sql: `UPDATE companies SET
       cover_letter_text = ?,
       cover_letter_replacements = ?,
       cv_modified_text = ?,
       cv_change_summary = ?,
       message_text = ?,
       fetched_context = ?,
       address = ?,
       status = 'generated',
       updated_at = datetime('now')
     WHERE id = ?`,
    args: [
      result.coverLetter,
      result.coverLetterReplacements ? JSON.stringify(result.coverLetterReplacements) : "",
      result.cvModifiedText,
      result.cvChangeSummary,
      result.messageText,
      fetchedContext,
      address,
      company.id,
    ],
  });

  return getCompany(company.id, company.user_id);
}

generateRouter.post("/:id", async (req, res) => {
  const company = await getCompany(req.params.id, req.session.userId);
  if (!company) return res.status(404).json({ error: "Introuvable" });
  try {
    const profile = await getProfile(req.session.userId);
    const updated = await generateForCompany(company, profile);
    res.json(updated);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Génère pour toutes les entreprises en attente, une par une.
generateRouter.post("/", async (req, res) => {
  const profile = await getProfile(req.session.userId);
  const { rows: pending } = await db.execute({
    sql: "SELECT * FROM companies WHERE user_id = ? AND status = 'pending' ORDER BY created_at ASC",
    args: [req.session.userId],
  });

  const results = [];
  for (const company of pending) {
    try {
      await generateForCompany(company, profile);
      results.push({ id: company.id, name: company.name, ok: true });
    } catch (err) {
      results.push({ id: company.id, name: company.name, ok: false, error: err.message });
    }
  }
  res.json({ processed: results.length, results });
});
