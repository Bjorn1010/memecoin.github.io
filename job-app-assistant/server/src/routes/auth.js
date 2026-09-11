import { Router } from "express";
import bcrypt from "bcryptjs";
import { createUser, getUserByEmail, getUserById } from "../db.js";

export const authRouter = Router();

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

authRouter.post("/signup", async (req, res) => {
  const { email, password, full_name } = req.body || {};
  const cleanEmail = (email || "").trim().toLowerCase();

  if (!EMAIL_RE.test(cleanEmail)) {
    return res.status(400).json({ error: "Adresse email invalide." });
  }
  if (!password || password.length < 8) {
    return res.status(400).json({ error: "Le mot de passe doit faire au moins 8 caractères." });
  }

  try {
    const existing = await getUserByEmail(cleanEmail);
    if (existing) {
      return res.status(409).json({ error: "Un compte existe déjà avec cet email." });
    }
    const passwordHash = await bcrypt.hash(password, 10);
    const user = await createUser({ email: cleanEmail, passwordHash, fullName: full_name });
    req.session.userId = user.id;
    res.status(201).json({ ok: true, email: user.email });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

authRouter.post("/login", async (req, res) => {
  const { email, password } = req.body || {};
  const cleanEmail = (email || "").trim().toLowerCase();

  try {
    const user = await getUserByEmail(cleanEmail);
    if (!user) {
      return res.status(401).json({ error: "Email ou mot de passe incorrect." });
    }
    const valid = await bcrypt.compare(password || "", user.password_hash);
    if (!valid) {
      return res.status(401).json({ error: "Email ou mot de passe incorrect." });
    }
    req.session.userId = user.id;
    res.json({ ok: true, email: user.email });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

authRouter.post("/logout", (req, res) => {
  req.session = null;
  res.json({ ok: true });
});

authRouter.get("/me", async (req, res) => {
  if (!req.session || !req.session.userId) {
    return res.json({ authed: false });
  }
  const user = await getUserById(req.session.userId);
  if (!user) {
    req.session = null;
    return res.json({ authed: false });
  }
  res.json({ authed: true, email: user.email });
});
