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
