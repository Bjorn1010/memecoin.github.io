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

// Couleur du texte normal de la lettre (voir word/styles.xml / runs non-accentués).
const BASE_TEXT_COLOR = "2B2B2B";

/**
 * Les emplacements à remplir étaient stylés en doré ou en gris italique
 * uniquement pour que l'auteur (et l'IA) les repère facilement dans le
 * modèle — ce n'est pas un style voulu dans la lettre finale. Une fois le
 * texte remplacé, on uniformise ces passages avec le reste du texte :
 * couleur normale, sans italique.
 */
function normalizeAccentRuns(xml) {
  return xml.replace(/<w:rPr>([\s\S]*?)<\/w:rPr>/g, (full, inner) => {
    const colorMatch = inner.match(/<w:color w:val="([0-9A-Fa-f]{6})"\s*\/>/);
    const color = colorMatch ? colorMatch[1].toUpperCase() : null;
    const isItalic = /<w:i\/>|<w:i\s+w:val="[^"]*"\/>/.test(inner);
    const isGold = color === "A08355";
    const isGrayItalic = color === "8A8A8A" && isItalic;
    if (!isGold && !isGrayItalic) return full;

    const newInner = inner
      .replace(/<w:i\/>/g, "")
      .replace(/<w:iCs\/>/g, "")
      .replace(/<w:color w:val="[0-9A-Fa-f]{6}"\s*\/>/, `<w:color w:val="${BASE_TEXT_COLOR}"/>`);
    return `<w:rPr>${newInner}</w:rPr>`;
  });
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Retire gras/italique/couleur d'un bloc <w:rPr> — utilisé sur les runs d'un
 * emplacement rempli par l'IA, pour que le texte inséré ait l'air d'avoir
 * toujours fait partie de la lettre plutôt que de ressortir en gras doré. */
function stripRunEmphasis(rPrInner) {
  return rPrInner
    .replace(/<w:b\/>/g, "")
    .replace(/<w:bCs\/>/g, "")
    .replace(/<w:i\/>/g, "")
    .replace(/<w:iCs\/>/g, "")
    .replace(/<w:color w:val="[0-9A-Fa-f]{6}"\s*\/>/, `<w:color w:val="${BASE_TEXT_COLOR}"/>`);
}

/**
 * Remplace chirurgicalement, directement dans le XML du .docx original, le
 * texte de chaque emplacement entre crochets par sa valeur — préserve à
 * 100% la mise en page, la police et le style du fichier d'origine puisque
 * rien d'autre n'est touché. Le run qui contenait l'emplacement perd son
 * gras/italique/couleur d'accent (c'était un repère de modèle, pas un style
 * voulu pour du texte final) pour se fondre naturellement dans la phrase.
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
      const runPattern = new RegExp(
        `<w:r>((?:(?!<w:r>|</w:r>)[\\s\\S])*?)<w:t([^>]*)>${escapeRegExp(variant)}</w:t></w:r>`
      );
      const match = xml.match(runPattern);
      if (match) {
        const [fullMatch, rPrBlock, tAttrs] = match;
        const newRPrBlock = rPrBlock.replace(
          /<w:rPr>([\s\S]*?)<\/w:rPr>/,
          (m, inner) => `<w:rPr>${stripRunEmphasis(inner)}</w:rPr>`
        );
        const newRun = `<w:r>${newRPrBlock}<w:t${tAttrs}>${escapedValue}</w:t></w:r>`;
        xml = xml.replace(fullMatch, newRun);
        break;
      }
      // Filet de sécurité si la structure du run ne correspond pas exactement
      // au motif attendu : on remplace au moins le texte, sans toucher au style.
      if (xml.includes(variant)) {
        xml = xml.split(variant).join(escapedValue);
        break;
      }
    }
  }

  // Passages dorés/gris-italique restants (ex: un titre statique qui n'était
  // pas un emplacement à remplir) : on ne touche qu'à la couleur/l'italique,
  // le gras éventuel (ex: un titre de section) reste inchangé.
  xml = normalizeAccentRuns(xml);

  zip.file(docPath, xml);
  return zip.generateAsync({ type: "nodebuffer" });
}

function unescapeXmlEntities(value) {
  return (value || "")
    .replace(/&apos;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

function escapeHtml(value) {
  return (value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

const JC_TO_CSS = { right: "right", center: "center", both: "justify", left: "left" };

/** Twentièmes de point (dxa), unité docx pour les marges/espacements -> points CSS. */
function dxaToPt(value) {
  return value == null ? null : Number(value) / 20;
}

/** Twentièmes de point -> pouces, pour les dimensions de page passées à Playwright. */
function dxaToInches(value) {
  return value == null ? null : Number(value) / 1440;
}

/**
 * Convertit le XML d'un .docx en un fragment HTML fidèle (alignement, gras,
 * italique, couleur, police et taille par run, espacement entre paragraphes),
 * pour pouvoir ensuite l'imprimer en PDF avec un moteur de rendu web. Renvoie
 * aussi la taille de page et les marges lues dans le document, pour que le
 * PDF garde la même mise en page que le fichier Word d'origine.
 */
export async function docxBufferToHtml(buffer) {
  const zip = await JSZip.loadAsync(buffer);
  const xml = await zip.file("word/document.xml").async("string");
  const defaultStyle = await extractDocxStyle(buffer);
  const defaultFont = defaultStyle.fontFamily || "Calibri";
  const defaultSizePt = defaultStyle.fontSize ? defaultStyle.fontSize / 2 : 11;

  const pgSzMatch = xml.match(/<w:pgSz\s+([^/]*)\/>/);
  const pgMarMatch = xml.match(/<w:pgMar\s+([^/]*)\/>/);
  const pgAttr = (attrs, name) => {
    if (!attrs) return null;
    const m = attrs.match(new RegExp(`w:${name}="(\\d+)"`));
    return m ? Number(m[1]) : null;
  };
  const page = {
    widthIn: dxaToInches(pgAttr(pgSzMatch?.[1], "w")) || 8.27,
    heightIn: dxaToInches(pgAttr(pgSzMatch?.[1], "h")) || 11.69,
    marginTopIn: dxaToInches(pgAttr(pgMarMatch?.[1], "top")) || 1,
    marginRightIn: dxaToInches(pgAttr(pgMarMatch?.[1], "right")) || 1,
    marginBottomIn: dxaToInches(pgAttr(pgMarMatch?.[1], "bottom")) || 1,
    marginLeftIn: dxaToInches(pgAttr(pgMarMatch?.[1], "left")) || 1,
  };

  const paragraphs = xml.match(/<w:p(?:\s[^>]*)?>[\s\S]*?<\/w:p>/g) || [];
  const bodyParas = paragraphs.filter((p) => !/<w:sectPr/.test(p) || /<w:r>/.test(p));

  const paraHtml = bodyParas.map((p) => {
    const pPrMatch = p.match(/<w:pPr>([\s\S]*?)<\/w:pPr>/);
    const pPr = pPrMatch ? pPrMatch[1] : "";
    const jcMatch = pPr.match(/<w:jc w:val="(\w+)"/);
    const textAlign = JC_TO_CSS[jcMatch?.[1]] || "left";
    const afterPt = dxaToPt(pPr.match(/<w:spacing[^>]*w:after="(\d+)"/)?.[1]) ?? 8;
    const beforePt = dxaToPt(pPr.match(/<w:spacing[^>]*w:before="(\d+)"/)?.[1]) ?? 0;

    const runs = p.match(/<w:r>[\s\S]*?<\/w:r>/g) || [];
    const runHtml = runs
      .map((r) => {
        const rPrMatch = r.match(/<w:rPr>([\s\S]*?)<\/w:rPr>/);
        const rPr = rPrMatch ? rPrMatch[1] : "";
        const bold = /<w:b\/>/.test(rPr);
        const italic = /<w:i\/>/.test(rPr);
        const color = rPr.match(/<w:color w:val="([0-9A-Fa-f]{6})"/)?.[1];
        const font = rPr.match(/<w:rFonts[^>]*w:ascii="([^"]+)"/)?.[1] || defaultFont;
        const szMatch = rPr.match(/<w:sz w:val="(\d+)"/);
        const sizePt = szMatch ? Number(szMatch[1]) / 2 : defaultSizePt;

        const textPieces = [...r.matchAll(/<w:t[^>]*>([^<]*)<\/w:t>/g)].map((m) =>
          escapeHtml(unescapeXmlEntities(m[1]))
        );
        const hasTab = /<w:tab\/>/.test(r);
        const text = textPieces.join("") + (hasTab ? "&emsp;" : "");
        if (!text) return "";

        const style = [
          `font-family:'${font}', sans-serif`,
          `font-size:${sizePt}pt`,
          bold ? "font-weight:bold" : "font-weight:normal",
          italic ? "font-style:italic" : "",
          color ? `color:#${color}` : "",
        ]
          .filter(Boolean)
          .join(";");
        return `<span style="${style}">${text}</span>`;
      })
      .join("");

    const style = [
      `text-align:${textAlign}`,
      `margin:${beforePt}pt 0 ${afterPt}pt 0`,
      "padding:0",
    ].join(";");
    return `<p style="${style}">${runHtml || "&nbsp;"}</p>`;
  });

  return {
    bodyHtml: paraHtml.join("\n"),
    page,
    defaultFont,
    defaultSizePt,
  };
}
