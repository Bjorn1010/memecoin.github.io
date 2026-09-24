// Génération procédurale des visuels de maillot (canvas 2D pur, sans Three.js).
// Utilisé à la fois pour les textures du modèle 3D et pour les vignettes plates
// de la boutique et du panier.

export const TEX_W = 768;
export const TEX_H = 1024;

/**
 * Silhouette du maillot, décrite une seule fois en coordonnées normalisées
 * (u : 0 = gauche, 1 = droite ; v : 0 = haut, 1 = bas). La vignette 2D et la
 * géométrie 3D en dérivent toutes les deux : elles ne peuvent pas diverger.
 * Parcours horaire depuis l'ourlet gauche.
 */
export const SILHOUETTE_PATH = [
  { type: 'M', u: 0.185, v: 0.965 },
  // Couture de côté gauche, légèrement cintrée
  { type: 'Q', cu: 0.19, cv: 0.6, u: 0.205, v: 0.35 },
  // Dessous de manche -> poignet
  { type: 'L', u: 0.06, v: 0.315 },
  { type: 'L', u: 0.015, v: 0.16 },
  // Épaule gauche
  { type: 'Q', cu: 0.13, cv: 0.06, u: 0.295, v: 0.045 },
  { type: 'L', u: 0.425, v: 0.008 },
  // Encolure
  { type: 'Q', cu: 0.5, cv: 0.085, u: 0.575, v: 0.008 },
  // Épaule droite
  { type: 'L', u: 0.705, v: 0.045 },
  { type: 'Q', cu: 0.87, cv: 0.06, u: 0.985, v: 0.16 },
  // Poignet -> dessous de manche droite
  { type: 'L', u: 0.94, v: 0.315 },
  { type: 'L', u: 0.795, v: 0.35 },
  // Couture de côté droite
  { type: 'Q', cu: 0.81, cv: 0.6, u: 0.815, v: 0.965 },
  // Ourlet légèrement arrondi
  { type: 'Q', cu: 0.5, cv: 0.99, u: 0.185, v: 0.965 },
];

/** Portion du tracé correspondant à l'encolure, pour dessiner le col côtelé. */
export const NECKLINE = { start: { u: 0.425, v: 0.008 }, control: { u: 0.5, cv: 0.085 }, end: { u: 0.575, v: 0.008 } };

/** Trace la silhouette du maillot dans un contexte 2D (repère canvas). */
export const traceJerseyPath = (ctx, w, h) => {
  ctx.beginPath();
  SILHOUETTE_PATH.forEach((segment) => {
    if (segment.type === 'M') ctx.moveTo(segment.u * w, segment.v * h);
    else if (segment.type === 'L') ctx.lineTo(segment.u * w, segment.v * h);
    else ctx.quadraticCurveTo(segment.cu * w, segment.cv * h, segment.u * w, segment.v * h);
  });
  ctx.closePath();
};

// #region Utilitaires couleur

const withAlpha = (hex, alpha) => {
  const value = hex.replace('#', '');
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

export const isLight = (hex) => {
  const value = hex.replace('#', '');
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 > 140;
};

// #region Couches de dessin

const drawFabricWeave = (ctx, w, h) => {
  const step = 6;
  ctx.save();
  for (let y = 0; y < h; y += step) {
    const offset = (y / step) % 2 === 0 ? 0 : step / 2;
    for (let x = 0; x < w; x += step) {
      ctx.fillStyle = 'rgba(255,255,255,0.035)';
      ctx.fillRect(x + offset, y, 2, 2);
      ctx.fillStyle = 'rgba(0,0,0,0.05)';
      ctx.fillRect(x + offset + 2, y + 2, 2, 2);
    }
  }
  ctx.restore();
};

const drawPattern = (ctx, w, h, design) => {
  const { secondary, accent, pattern } = design;
  ctx.save();
  switch (pattern) {
    case 'stripes': {
      const bandWidth = w / 9;
      ctx.fillStyle = withAlpha(secondary, 0.85);
      for (let i = 1; i < 9; i += 2) ctx.fillRect(i * bandWidth, 0, bandWidth, h);
      break;
    }
    case 'pinstripe': {
      ctx.strokeStyle = withAlpha(secondary, 0.55);
      ctx.lineWidth = 3;
      for (let x = w * 0.1; x < w * 0.9; x += w / 18) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      break;
    }
    case 'sash': {
      ctx.fillStyle = withAlpha(secondary, 0.95);
      ctx.beginPath();
      ctx.moveTo(0, h * 0.28);
      ctx.lineTo(w, h * 0.62);
      ctx.lineTo(w, h * 0.78);
      ctx.lineTo(0, h * 0.44);
      ctx.closePath();
      ctx.fill();
      break;
    }
    case 'gradient': {
      const gradient = ctx.createLinearGradient(0, h, 0, h * 0.15);
      gradient.addColorStop(0, withAlpha(secondary, 0.9));
      gradient.addColorStop(0.45, withAlpha(secondary, 0.25));
      gradient.addColorStop(1, withAlpha(secondary, 0));
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, w, h);
      break;
    }
    case 'blocks': {
      ctx.fillStyle = withAlpha(accent, 0.35);
      ctx.fillRect(0, h * 0.34, w, h * 0.12);
      ctx.fillStyle = withAlpha(secondary, 0.22);
      ctx.fillRect(0, h * 0.46, w, h * 0.05);
      break;
    }
    case 'mesh': {
      ctx.fillStyle = withAlpha(secondary, 0.4);
      ctx.fillRect(0, h * 0.2, w * 0.13, h * 0.7);
      ctx.fillRect(w * 0.87, h * 0.2, w * 0.13, h * 0.7);
      ctx.fillStyle = 'rgba(0,0,0,0.25)';
      for (let y = h * 0.2; y < h * 0.9; y += 10) {
        ctx.fillRect(0, y, w * 0.13, 4);
        ctx.fillRect(w * 0.87, y, w * 0.13, 4);
      }
      break;
    }
    default:
      break;
  }
  ctx.restore();
};

// Finitions du vêtement : col côtelé, bords de manche, ourlet.
const drawTrims = (ctx, w, h, design) => {
  const { secondary } = design;
  const ribWidth = h * 0.028;

  ctx.save();

  // Col côtelé : on suit la courbe de l'encolure.
  ctx.lineWidth = ribWidth;
  ctx.lineCap = 'round';
  ctx.strokeStyle = secondary;
  ctx.beginPath();
  ctx.moveTo(NECKLINE.start.u * w, NECKLINE.start.v * h);
  ctx.quadraticCurveTo(NECKLINE.control.u * w, NECKLINE.control.cv * h, NECKLINE.end.u * w, NECKLINE.end.v * h);
  ctx.stroke();
  // Côtes du col
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = 'rgba(0,0,0,0.22)';
  for (let t = 0.08; t < 0.95; t += 0.06) {
    const u = 0.425 + (0.575 - 0.425) * t;
    const v = (1 - t) * (1 - t) * 0.008 + 2 * (1 - t) * t * 0.085 + t * t * 0.008;
    ctx.beginPath();
    ctx.moveTo(u * w, v * h - ribWidth / 2);
    ctx.lineTo(u * w, v * h + ribWidth / 2);
    ctx.stroke();
  }

  // Bords de manche : trait épais le long du bord du poignet. La moitié
  // extérieure sera découpée par la silhouette, il reste une bande nette.
  ctx.strokeStyle = withAlpha(secondary, 0.92);
  ctx.lineWidth = h * 0.062;
  ctx.lineCap = 'butt';
  ctx.beginPath();
  ctx.moveTo(0.015 * w, 0.16 * h);
  ctx.lineTo(0.06 * w, 0.315 * h);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(0.985 * w, 0.16 * h);
  ctx.lineTo(0.94 * w, 0.315 * h);
  ctx.stroke();

  // Ourlet : trait le long de la courbe du bas
  ctx.strokeStyle = withAlpha(secondary, 0.55);
  ctx.lineWidth = h * 0.05;
  ctx.beginPath();
  ctx.moveTo(0.815 * w, 0.965 * h);
  ctx.quadraticCurveTo(0.5 * w, 0.99 * h, 0.185 * w, 0.965 * h);
  ctx.stroke();

  ctx.restore();
};

// Coutures d'emmanchure : de l'épaule au creux de l'aisselle.
const drawSeams = (ctx, w, h) => {
  ctx.save();
  ctx.strokeStyle = 'rgba(0,0,0,0.32)';
  ctx.setLineDash([6, 5]);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(w * 0.295, h * 0.05);
  ctx.quadraticCurveTo(w * 0.235, h * 0.18, w * 0.205, h * 0.35);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(w * 0.705, h * 0.05);
  ctx.quadraticCurveTo(w * 0.765, h * 0.18, w * 0.795, h * 0.35);
  ctx.stroke();
  ctx.restore();
};

const drawShading = (ctx, w, h) => {
  ctx.save();
  const vignette = ctx.createRadialGradient(w / 2, h * 0.45, w * 0.1, w / 2, h * 0.5, w * 0.78);
  vignette.addColorStop(0, 'rgba(255,255,255,0.08)');
  vignette.addColorStop(0.6, 'rgba(0,0,0,0)');
  vignette.addColorStop(1, 'rgba(0,0,0,0.35)');
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, w, h);

  const fold = ctx.createLinearGradient(w * 0.35, 0, w * 0.65, 0);
  fold.addColorStop(0, 'rgba(0,0,0,0.08)');
  fold.addColorStop(0.5, 'rgba(255,255,255,0.05)');
  fold.addColorStop(1, 'rgba(0,0,0,0.08)');
  ctx.fillStyle = fold;
  ctx.fillRect(w * 0.35, 0, w * 0.3, h);
  ctx.restore();
};

const drawNumber = (ctx, w, text, fill, outline, centerY, size) => {
  ctx.save();
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = `italic 900 ${size}px "Arial Black", Arial, sans-serif`;
  ctx.lineJoin = 'round';
  ctx.fillStyle = 'rgba(0,0,0,0.35)';
  ctx.fillText(text, w / 2 + size * 0.02, centerY + size * 0.025);
  ctx.lineWidth = size * 0.09;
  ctx.strokeStyle = outline;
  ctx.strokeText(text, w / 2, centerY);
  ctx.fillStyle = fill;
  ctx.fillText(text, w / 2, centerY);
  ctx.restore();
};

const drawArcName = (ctx, w, text, fill, outline, centerY, radius, size) => {
  const chars = [...text.toUpperCase()];
  if (!chars.length) return;
  ctx.save();
  ctx.translate(w / 2, centerY + radius);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = `900 ${size}px "Arial Black", Arial, sans-serif`;
  ctx.lineJoin = 'round';

  const spread = Math.min(Math.PI * 0.62, chars.length * 0.17);
  const step = chars.length > 1 ? spread / (chars.length - 1) : 0;
  let angle = -spread / 2;

  chars.forEach((char) => {
    ctx.save();
    ctx.rotate(angle);
    ctx.translate(0, -radius);
    ctx.lineWidth = size * 0.16;
    ctx.strokeStyle = outline;
    ctx.strokeText(char, 0, 0);
    ctx.fillStyle = fill;
    ctx.fillText(char, 0, 0);
    ctx.restore();
    angle += step;
  });
  ctx.restore();
};

const drawWordmark = (ctx, w, y, color, size) => {
  ctx.save();
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = `italic 900 ${size}px Arial, Helvetica, sans-serif`;
  ctx.fillStyle = color;
  ctx.fillText('ONZE', w / 2, y);
  const width = ctx.measureText('ONZE').width;
  ctx.fillRect(w / 2 - width / 2, y + size * 0.62, width * 0.78, Math.max(2, size * 0.09));
  ctx.restore();
};

const drawCrest = (ctx, x, y, size, design) => {
  ctx.save();
  ctx.translate(x, y);
  ctx.beginPath();
  ctx.moveTo(-size / 2, -size / 2);
  ctx.lineTo(size / 2, -size / 2);
  ctx.lineTo(size / 2, size * 0.18);
  ctx.quadraticCurveTo(size / 2, size / 2, 0, size / 2);
  ctx.quadraticCurveTo(-size / 2, size / 2, -size / 2, size * 0.18);
  ctx.closePath();
  ctx.fillStyle = withAlpha(design.accent, 0.95);
  ctx.fill();
  ctx.lineWidth = Math.max(2, size * 0.06);
  ctx.strokeStyle = 'rgba(0,0,0,0.35)';
  ctx.stroke();

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = `900 ${size * 0.46}px Arial, sans-serif`;
  ctx.fillStyle = isLight(design.accent) ? '#111' : '#fff';
  ctx.fillText('11', 0, -size * 0.02);
  ctx.restore();
};

const baseCanvas = (design) => {
  const canvas = document.createElement('canvas');
  canvas.width = TEX_W;
  canvas.height = TEX_H;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = design.primary;
  ctx.fillRect(0, 0, TEX_W, TEX_H);
  drawPattern(ctx, TEX_W, TEX_H, design);
  drawFabricWeave(ctx, TEX_W, TEX_H);
  drawTrims(ctx, TEX_W, TEX_H, design);
  return { canvas, ctx };
};

/**
 * Textures recto / verso d'un maillot.
 * @param {object} design entrée du catalogue
 * @param {{name?: string, number?: string|number}} flocage
 */
export const createJerseyTextures = (design, flocage = {}) => {
  const light = isLight(design.primary);
  const inkFill = light ? '#12141a' : '#ffffff';
  const inkOutline = withAlpha(design.secondary, 0.95);
  const number = (flocage.number ?? design.number ?? '').toString().slice(0, 2);
  const name = (flocage.name ?? '').toString().slice(0, 12);

  const front = baseCanvas(design);
  drawWordmark(front.ctx, TEX_W, TEX_H * 0.2, inkFill, TEX_H * 0.052);
  drawCrest(front.ctx, TEX_W * 0.72, TEX_H * 0.235, TEX_H * 0.075, design);
  if (number) drawNumber(front.ctx, TEX_W, number, inkFill, inkOutline, TEX_H * 0.45, TEX_H * 0.17);
  front.ctx.save();
  front.ctx.textAlign = 'center';
  front.ctx.font = `700 ${TEX_H * 0.021}px Arial, sans-serif`;
  front.ctx.fillStyle = withAlpha(light ? '#12141a' : '#ffffff', 0.75);
  front.ctx.fillText(`${design.name1.toUpperCase()} ${design.name2.toUpperCase()}`, TEX_W / 2, TEX_H * 0.565);
  front.ctx.restore();
  drawSeams(front.ctx, TEX_W, TEX_H);
  drawShading(front.ctx, TEX_W, TEX_H);

  const back = baseCanvas(design);
  if (name) drawArcName(back.ctx, TEX_W, name, inkFill, inkOutline, TEX_H * 0.17, TEX_H * 0.16, TEX_H * 0.055);
  if (number) drawNumber(back.ctx, TEX_W, number, inkFill, inkOutline, TEX_H * 0.5, TEX_H * 0.32);
  drawSeams(back.ctx, TEX_W, TEX_H);
  drawShading(back.ctx, TEX_W, TEX_H);

  return { front: front.canvas, back: back.canvas };
};

/**
 * Rend un maillot « à plat » découpé dans sa silhouette, pour les vignettes.
 * @param {HTMLCanvasElement} canvas cible
 * @param {object} design entrée du catalogue
 * @param {{face?: 'front'|'back', flocage?: object}} options
 */
export const drawJerseyFlat = (canvas, design, options = {}) => {
  const { face = 'front', flocage = {} } = options;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const width = canvas.clientWidth || 320;
  const height = Math.round((width * TEX_H) / TEX_W);

  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.height = `${height}px`;

  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const textures = createJerseyTextures(design, flocage);
  const source = textures[face];

  ctx.save();
  traceJerseyPath(ctx, width, height);
  ctx.clip();
  ctx.drawImage(source, 0, 0, width, height);
  ctx.restore();

  // Liseré de contour pour détacher le maillot du fond
  ctx.save();
  traceJerseyPath(ctx, width, height);
  ctx.lineWidth = Math.max(1, width * 0.006);
  ctx.strokeStyle = 'rgba(255,255,255,0.18)';
  ctx.stroke();
  ctx.restore();

  return canvas;
};
