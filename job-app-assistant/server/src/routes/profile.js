import { Router } from "express";
import multer from "multer";
import { getProfile, updateProfile } from "../db.js";
import { extractTextFromDocx, extractDocxStyle } from "../services/docx.js";

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });

export const profileRouter = Router();

const BULLETIN_SLOTS = [1, 2, 3];

function serializeProfile(p) {
  const out = {
    full_name: p.full_name,
    cv_text: p.cv_text,
    cv_filename: p.cv_filename,
    has_cv_docx: !!p.cv_docx,
    cover_letter_text: p.cover_letter_text,
  };
  for (const n of BULLETIN_SLOTS) {
    out[`bulletin${n}_filename`] = p[`bulletin${n}_filename`];
    out[`has_bulletin${n}`] = !!p[`bulletin${n}_file`];
  }
  return out;
}

profileRouter.get("/", (req, res) => {
  res.json(serializeProfile(getProfile()));
});

profileRouter.put("/", (req, res) => {
  const { full_name, cover_letter_text } = req.body || {};
  updateProfile({
    full_name: full_name ?? "",
    cover_letter_text: cover_letter_text ?? "",
  });
  res.json(serializeProfile(getProfile()));
});

profileRouter.get("/cv", (req, res) => {
  const p = getProfile();
  if (!p.cv_docx) return res.status(404).json({ error: "Aucun CV importé" });
  res.setHeader(
    "Content-Type",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  );
  res.setHeader("Content-Disposition", `attachment; filename="${p.cv_filename || "CV.docx"}"`);
  res.send(p.cv_docx);
});

profileRouter.post("/cv", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: "Aucun fichier reçu" });
    const text = await extractTextFromDocx(req.file.buffer);
    const style = await extractDocxStyle(req.file.buffer);
    updateProfile({
      cv_docx: req.file.buffer,
      cv_filename: req.file.originalname,
      cv_text: text,
      cv_font_family: style.fontFamily || "",
      cv_font_size: style.fontSize,
    });
    res.json(serializeProfile(getProfile()));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

profileRouter.post("/cover-letter", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: "Aucun fichier reçu" });
    const text = await extractTextFromDocx(req.file.buffer);
    const style = await extractDocxStyle(req.file.buffer);
    updateProfile({
      cover_letter_text: text,
      cover_letter_font_family: style.fontFamily || "",
      cover_letter_font_size: style.fontSize,
    });
    res.json(serializeProfile(getProfile()));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

for (const n of BULLETIN_SLOTS) {
  profileRouter.get(`/bulletin${n}`, (req, res) => {
    const p = getProfile();
    const file = p[`bulletin${n}_file`];
    if (!file) return res.status(404).json({ error: "Aucun bulletin importé pour ce créneau" });
    res.setHeader("Content-Type", p[`bulletin${n}_mimetype`] || "application/octet-stream");
    res.setHeader(
      "Content-Disposition",
      `attachment; filename="${p[`bulletin${n}_filename`] || `bulletin-${n}`}"`
    );
    res.send(file);
  });

  profileRouter.post(`/bulletin${n}`, upload.single("file"), (req, res) => {
    if (!req.file) return res.status(400).json({ error: "Aucun fichier reçu" });
    updateProfile({
      [`bulletin${n}_file`]: req.file.buffer,
      [`bulletin${n}_filename`]: req.file.originalname,
      [`bulletin${n}_mimetype`]: req.file.mimetype,
    });
    res.json(serializeProfile(getProfile()));
  });
}
