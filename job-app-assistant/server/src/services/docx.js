import mammoth from "mammoth";
import JSZip from "jszip";
import { Document, Packer, Paragraph, TextRun } from "docx";

/** Extrait le texte brut d'un buffer .docx */
export async function extractTextFromDocx(buffer) {
  const result = await mammoth.extractRawText({ buffer });
  return result.value.trim();
}

/**
 * Détecte la police et la taille de texte par défaut d'un .docx (lues dans
 * word/styles.xml) pour pouvoir régénérer des documents qui gardent le même
 * style visuel — l'IA ne doit changer que le texte, pas la mise en forme.
 * Renvoie { fontFamily, fontSize } (fontSize en demi-points, unité Word), ou
 * des valeurs nulles si indétectable.
 */
export async function extractDocxStyle(buffer) {
  try {
    const zip = await JSZip.loadAsync(buffer);
    const stylesXml = await zip.file("word/styles.xml")?.async("string");
    if (!stylesXml) return { fontFamily: null, fontSize: null };

    const defaultsMatch = stylesXml.match(/<w:docDefaults>[\s\S]*?<\/w:docDefaults>/);
    const scope = defaultsMatch ? defaultsMatch[0] : stylesXml;

    const fontMatch = scope.match(/<w:rFonts[^>]*w:ascii="([^"]+)"/);
    const szMatch = scope.match(/<w:sz w:val="(\d+)"/);

    return {
      fontFamily: fontMatch ? fontMatch[1] : null,
      fontSize: szMatch ? Number(szMatch[1]) : null,
    };
  } catch {
    return { fontFamily: null, fontSize: null };
  }
}

/**
 * Génère un .docx propre à partir d'un texte brut (paragraphes séparés par
 * des sauts de ligne), en réutilisant si possible la police/taille du
 * document original du candidat pour que seul le texte change.
 */
export async function textToDocxBuffer(
  text,
  { title, fontFamily, fontSize } = {}
) {
  const font = fontFamily || "Calibri";
  const size = fontSize || 22;
  const paragraphs = [];

  if (title) {
    paragraphs.push(
      new Paragraph({
        children: [new TextRun({ text: title, bold: true, font, size: size + 6 })],
        spacing: { after: 200 },
      })
    );
  }

  const blocks = (text || "").split(/\n{2,}/);
  for (const block of blocks) {
    const lines = block.split("\n");
    for (const line of lines) {
      paragraphs.push(
        new Paragraph({
          children: [new TextRun({ text: line, font, size })],
        })
      );
    }
    paragraphs.push(new Paragraph({ text: "" }));
  }

  const doc = new Document({
    sections: [{ properties: {}, children: paragraphs }],
  });

  return Packer.toBuffer(doc);
}

function escapeXml(value) {
  return (value || "")
    .toString()
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Remplace chaque emplacement entre crochets par sa valeur dans un texte brut
 * (utilisé pour construire un aperçu texte à partir du dictionnaire renvoyé
 * par l'IA, indépendamment de la génération du .docx).
 */
export function applyReplacements(text, replacements) {
  let result = text || "";
  for (const [placeholder, value] of Object.entries(replacements || {})) {
    result = result.split(placeholder).join(value || "");
  }
  return result;
}

/**
 * Remplace chirurgicalement, directement dans le XML du .docx original, le
 * texte de chaque emplacement entre crochets par sa valeur — préserve à
 * 100% la mise en page, la police et le style du fichier d'origine puisque
 * rien d'autre n'est touché.
 */
export async function fillDocxTemplate(buffer, replacements) {
  const zip = await JSZip.loadAsync(buffer);
  const docPath = "word/document.xml";
  const file = zip.file(docPath);
  if (!file) throw new Error("Fichier .docx invalide (document.xml introuvable).");
  let xml = await file.async("string");

  for (const [placeholder, rawValue] of Object.entries(replacements || {})) {
    const escapedValue = escapeXml(rawValue);
    const variants = [
      escapeXml(placeholder).replace(/'/g, "&apos;").replace(/"/g, "&quot;"),
      escapeXml(placeholder),
    ];
    for (const variant of variants) {
      if (xml.includes(variant)) {
        xml = xml.split(variant).join(escapedValue);
        break;
      }
    }
  }

  zip.file(docPath, xml);
  return zip.generateAsync({ type: "nodebuffer" });
}
