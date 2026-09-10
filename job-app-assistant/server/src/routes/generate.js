import { Router } from "express";
import { db, getProfile } from "../db.js";
import { fetchCompanyContext } from "../services/fetchCompany.js";
import { generateApplication } from "../services/ai.js";

export const generateRouter = Router();

async function generateForCompany(company, profile) {
  const fetchedContext = company.url
    ? await fetchCompanyContext(company.url)
    : "";

  const result = await generateApplication({
    fullName: profile.full_name,
    cvText: profile.cv_text,
    baseCoverLetter: profile.cover_letter_text,
    companyName: company.name,
    companyDescription: company.description,
    fetchedContext,
    source: company.source,
  });

  db.prepare(
    `UPDATE companies SET
       cover_letter_text = @cover_letter_text,
       cv_modified_text = @cv_modified_text,
       cv_change_summary = @cv_change_summary,
       message_text = @message_text,
       fetched_context = @fetched_context,
       status = 'generated',
       updated_at = datetime('now')
     WHERE id = @id`
  ).run({
    id: company.id,
    cover_letter_text: result.coverLetter,
    cv_modified_text: result.cvModifiedText,
    cv_change_summary: result.cvChangeSummary,
    message_text: result.messageText,
    fetched_context: fetchedContext,
  });

  return db.prepare("SELECT * FROM companies WHERE id = ?").get(company.id);
}

generateRouter.post("/:id", async (req, res) => {
  const company = db.prepare("SELECT * FROM companies WHERE id = ?").get(req.params.id);
  if (!company) return res.status(404).json({ error: "Introuvable" });
  try {
    const profile = getProfile();
    const updated = await generateForCompany(company, profile);
    res.json(updated);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Génère pour toutes les entreprises en attente, une par une.
generateRouter.post("/", async (req, res) => {
  const profile = getProfile();
  const pending = db
    .prepare("SELECT * FROM companies WHERE status = 'pending' ORDER BY created_at ASC")
    .all();

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
