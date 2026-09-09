import mammoth from "mammoth";
import { Document, Packer, Paragraph, TextRun } from "docx";

/** Extrait le texte brut d'un buffer .docx */
export async function extractTextFromDocx(buffer) {
  const result = await mammoth.extractRawText({ buffer });
  return result.value.trim();
}

/**
 * Génère un .docx propre et professionnel à partir d'un texte brut
 * (paragraphes séparés par des sauts de ligne). Utilisé pour la lettre de
 * motivation adaptée, et pour le CV si des modifications ont été appliquées.
 */
export async function textToDocxBuffer(text, { title } = {}) {
  const paragraphs = [];

  if (title) {
    paragraphs.push(
      new Paragraph({
        children: [new TextRun({ text: title, bold: true, size: 28 })],
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
          children: [new TextRun({ text: line, size: 22 })],
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
