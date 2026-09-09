import { Router } from "express";

export const authRouter = Router();

authRouter.post("/login", (req, res) => {
  const { password } = req.body || {};
  if (!process.env.APP_PASSWORD) {
    return res
      .status(500)
      .json({ error: "APP_PASSWORD non configuré côté serveur (fichier .env)" });
  }
  if (password === process.env.APP_PASSWORD) {
    req.session.authed = true;
    return res.json({ ok: true });
  }
  return res.status(401).json({ error: "Mot de passe incorrect" });
});

authRouter.post("/logout", (req, res) => {
  req.session = null;
  res.json({ ok: true });
});

authRouter.get("/me", (req, res) => {
  res.json({ authed: !!(req.session && req.session.authed) });
});
