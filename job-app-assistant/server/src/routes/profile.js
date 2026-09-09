import { Router } from "express";
import multer from "multer";
import { getProfile, updateProfile } from "../db.js";
import { extractTextFromDocx } from "../services/docx.js";

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });

export const profileRouter = Router();

function serializeProfile(p) {
  return {
    full_name: p.full_name,
    cv_text: p.cv_text,
    cv_filename: p.cv_filename,
    has_cv_docx: !!p.cv_docx,
    cover_letter_text: p.cover_letter_text,
    smtp_host: p.smtp_host,
    smtp_port: p.smtp_port,
    smtp_secure: !!p.smtp_secure,
    smtp_user: p.smtp_user,
    smtp_pass_set: !!p.smtp_pass,
    smtp_from_name: p.smtp_from_name,
    smtp_from_email: p.smtp_from_email,
  };
}

profileRouter.get("/", (req, res) => {
  res.json(serializeProfile(getProfile()));
});

profileRouter.put("/", (req, res) => {
  const {
    full_name,
    cover_letter_text,
    smtp_host,
    smtp_port,
    smtp_secure,
    smtp_user,
    smtp_pass,
    smtp_from_name,
    smtp_from_email,
  } = req.body || {};

  const fields = {
    full_name: full_name ?? "",
    cover_letter_text: cover_letter_text ?? "",
    smtp_host: smtp_host ?? "",
    smtp_port: Number(smtp_port) || 587,
    smtp_secure: smtp_secure ? 1 : 0,
    smtp_user: smtp_user ?? "",
    smtp_from_name: smtp_from_name ?? "",
    smtp_from_email: smtp_from_email ?? "",
  };
  // Ne change le mot de passe SMTP que si un nouveau est fourni (évite d'écraser avec vide)
  if (smtp_pass) fields.smtp_pass = smtp_pass;

  const updated = updateProfile(fields);
  res.json(serializeProfile(updated));
});

profileRouter.post("/cv", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: "Aucun fichier reçu" });
    const text = await extractTextFromDocx(req.file.buffer);
    const updated = updateProfile({
      cv_docx: req.file.buffer,
      cv_filename: req.file.originalname,
      cv_text: text,
    });
    res.json(serializeProfile(updated));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});
