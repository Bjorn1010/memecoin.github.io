import { chromium } from "playwright";
import { docxBufferToHtml } from "./docx.js";

// Un seul navigateur headless réutilisé entre les requêtes plutôt que d'en
// relancer un par conversion (coûteux) — démarré à la demande, gardé ouvert.
let browserPromise = null;
function getBrowser() {
  if (!browserPromise) {
    browserPromise = chromium.launch({ args: ["--no-sandbox"] });
  }
  return browserPromise;
}

/**
 * Convertit un .docx en PDF en le transformant d'abord en HTML fidèle
 * (police, taille, gras/italique, couleur, alignement, marges de page —
 * voir docxBufferToHtml) puis en l'imprimant avec Chromium. Le rendu n'est
 * pas pixel pour pixel identique à Word, mais très proche, sans dépendre
 * d'un logiciel bureautique externe.
 */
export async function docxBufferToPdf(buffer) {
  const { bodyHtml, page: pageLayout, defaultFont, defaultSizePt } = await docxBufferToHtml(buffer);

  const html = `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: ${pageLayout.widthIn}in ${pageLayout.heightIn}in; margin: 0; }
  html, body {
    margin: 0;
    padding: 0;
    font-family: '${defaultFont}', sans-serif;
    font-size: ${defaultSizePt}pt;
    color: #2B2B2B;
  }
  p { padding: 0; }
</style>
</head>
<body>
${bodyHtml}
</body>
</html>`;

  const browser = await getBrowser();
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await page.setContent(html, { waitUntil: "networkidle" });
    const pdf = await page.pdf({
      printBackground: true,
      margin: {
        top: `${pageLayout.marginTopIn}in`,
        right: `${pageLayout.marginRightIn}in`,
        bottom: `${pageLayout.marginBottomIn}in`,
        left: `${pageLayout.marginLeftIn}in`,
      },
      width: `${pageLayout.widthIn}in`,
      height: `${pageLayout.heightIn}in`,
    });
    return pdf;
  } finally {
    await context.close();
  }
}
