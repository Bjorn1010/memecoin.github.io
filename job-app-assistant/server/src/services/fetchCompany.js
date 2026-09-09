import * as cheerio from "cheerio";

/**
 * Récupère et nettoie le texte visible d'une page web (offre d'emploi, page
 * "à propos", etc.) pour donner du contexte à l'IA. Best-effort : si la page
 * n'est pas accessible, on renvoie une chaîne vide plutôt que d'échouer.
 */
export async function fetchCompanyContext(url) {
  if (!url) return "";
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (compatible; JobAppAssistant/1.0; +https://example.com)",
      },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return "";
    const html = await res.text();
    const $ = cheerio.load(html);
    $("script, style, nav, footer, noscript").remove();
    const text = $("body").text().replace(/\s+/g, " ").trim();
    return text.slice(0, 8000);
  } catch {
    return "";
  }
}
