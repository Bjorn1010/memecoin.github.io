import nodemailer from "nodemailer";

/** Construit un transporteur nodemailer à partir de la config SMTP du profil. */
export function buildTransport(profile) {
  if (!profile.smtp_host || !profile.smtp_user || !profile.smtp_pass) {
    throw new Error(
      "Configuration SMTP incomplète. Renseigne-la dans la page Profil (hôte, utilisateur, mot de passe)."
    );
  }
  return nodemailer.createTransport({
    host: profile.smtp_host,
    port: profile.smtp_port || 587,
    secure: !!profile.smtp_secure,
    auth: {
      user: profile.smtp_user,
      pass: profile.smtp_pass,
    },
    // Certains hébergeurs (dont Render) ont un chemin IPv6 cassé vers Gmail :
    // la connexion reste bloquée jusqu'au timeout de la plateforme (→ 502) au
    // lieu d'échouer proprement. On force IPv4 et on met des délais courts
    // pour échouer vite avec un message clair.
    family: 4,
    connectionTimeout: 15000,
    greetingTimeout: 15000,
    socketTimeout: 20000,
  });
}

export async function sendApplicationEmail({
  profile,
  to,
  subject,
  body,
  attachments,
}) {
  if (!to) {
    throw new Error(
      "Aucune adresse email de contact pour cette entreprise. Renseigne-la avant d'envoyer."
    );
  }
  const transporter = buildTransport(profile);
  const fromName = profile.smtp_from_name || profile.full_name || "";
  const fromEmail = profile.smtp_from_email || profile.smtp_user;

  await transporter.sendMail({
    from: fromName ? `"${fromName}" <${fromEmail}>` : fromEmail,
    to,
    subject,
    text: body,
    attachments,
  });
}
