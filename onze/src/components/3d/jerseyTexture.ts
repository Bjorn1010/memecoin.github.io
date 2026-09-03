import * as THREE from "three";
import type { Colorway } from "@/lib/types";

/* Paints a kit onto a 2D canvas and hands back a THREE texture. Drawing it
 * rather than loading an image means the 3D hero ships zero texture bytes and
 * can restyle instantly when the colourway changes — no network, no decode.
 *
 * Everything is clipped to the garment silhouette and the surrounding pixels
 * are left fully transparent, so the mesh reads as a jersey rather than as a
 * rectangle of fabric. The material pairs this with alphaTest to discard those
 * pixels outright. */

const SIZE = 1024;

/* Same outline as the SVG <Jersey>, in its own -20..220 × 0..260 space. Kept
 * identical on purpose: the 3D hero and the 2D fallback must be the same
 * garment, or swapping between them on resize is visible. */
const BODY =
  "M100 26 L143 12 C152 9 160 13 168 20 L214 58 C220 63 220 71 215 77 L192 104 C188 109 181 109 177 105 L168 96 L168 236 C168 244 162 250 154 250 L46 250 C38 250 32 244 32 236 L32 96 L23 105 C19 109 12 109 8 104 L-15 77 C-20 71 -20 63 -14 58 L32 20 C40 13 48 9 57 12 L100 26 Z";

const VB = { x: -20, y: 0, w: 240, h: 260 };

export function createJerseyTexture(colorway: Colorway, monogram: string, number: string) {
  const canvas = document.createElement("canvas");
  canvas.width = SIZE;
  canvas.height = SIZE;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  const { primary, secondary, accent, pattern } = colorway;

  /* Map the SVG viewBox onto the square texture, then clip to the outline.
     Every paint below lands inside the garment only. */
  const sx = SIZE / VB.w;
  const sy = SIZE / VB.h;
  ctx.save();
  ctx.scale(sx, sy);
  ctx.translate(-VB.x, -VB.y);
  ctx.clip(new Path2D(BODY));
  /* Back to texture space for the fills, keeping the clip active. */
  ctx.setTransform(1, 0, 0, 1, 0, 0);

  ctx.fillStyle = primary;
  ctx.fillRect(0, 0, SIZE, SIZE);

  switch (pattern) {
    case "stripes": {
      ctx.fillStyle = secondary;
      const band = SIZE / 12;
      for (let x = 0; x < SIZE; x += band * 2) ctx.fillRect(x, 0, band, SIZE);
      break;
    }
    case "hoops": {
      ctx.fillStyle = secondary;
      const band = SIZE / 10;
      for (let y = 0; y < SIZE; y += band * 2) ctx.fillRect(0, y, SIZE, band);
      break;
    }
    case "halves": {
      ctx.fillStyle = secondary;
      ctx.fillRect(SIZE / 2, 0, SIZE / 2, SIZE);
      break;
    }
    case "sash": {
      ctx.fillStyle = secondary;
      ctx.beginPath();
      ctx.moveTo(0, SIZE * 0.78);
      ctx.lineTo(SIZE * 0.92, SIZE * 0.1);
      ctx.lineTo(SIZE * 0.92, SIZE * 0.36);
      ctx.lineTo(0, SIZE);
      ctx.closePath();
      ctx.fill();
      break;
    }
    case "gradient": {
      const g = ctx.createLinearGradient(0, 0, SIZE * 0.7, SIZE);
      g.addColorStop(0, primary);
      g.addColorStop(1, secondary);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, SIZE, SIZE);
      break;
    }
  }

  /* Woven texture. Without it the fabric reads as flat plastic under the
     specular highlight. */
  ctx.globalAlpha = 0.05;
  ctx.strokeStyle = "#000";
  ctx.lineWidth = 1;
  for (let y = 0; y < SIZE; y += 4) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(SIZE, y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  /* Sleeve cuffs and hem, positioned to match the outline's arms and waist. */
  ctx.fillStyle = accent;
  ctx.globalAlpha = 0.9;
  ctx.fillRect(0, SIZE * 0.335, SIZE * 0.24, SIZE * 0.036);
  ctx.fillRect(SIZE * 0.76, SIZE * 0.335, SIZE * 0.24, SIZE * 0.036);
  ctx.globalAlpha = 0.6;
  ctx.fillRect(SIZE * 0.21, SIZE * 0.945, SIZE * 0.58, SIZE * 0.024);
  ctx.globalAlpha = 1;

  /* Collar. */
  ctx.fillStyle = accent;
  ctx.globalAlpha = 0.92;
  ctx.beginPath();
  ctx.ellipse(SIZE * 0.5, SIZE * 0.1, SIZE * 0.115, SIZE * 0.055, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;

  /* Squad number, centred on the torso. */
  ctx.fillStyle = accent;
  ctx.globalAlpha = 0.3;
  ctx.font = `800 ${SIZE * 0.34}px Archivo, Arial Narrow, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(number, SIZE * 0.5, SIZE * 0.62);
  ctx.globalAlpha = 1;

  /* Crest stand-in, upper chest. */
  ctx.fillStyle = accent;
  ctx.font = `800 ${SIZE * 0.05}px Archivo, Arial Narrow, sans-serif`;
  ctx.fillText(monogram, SIZE * 0.66, SIZE * 0.28);

  /* Shading, still inside the clip: a diagonal falloff plus a soft key
     highlight, so the flat fill gains volume before the lights touch it. */
  const shade = ctx.createLinearGradient(0, 0, SIZE, SIZE);
  shade.addColorStop(0, "rgba(255,255,255,0.20)");
  shade.addColorStop(0.45, "rgba(255,255,255,0.02)");
  shade.addColorStop(1, "rgba(0,0,0,0.38)");
  ctx.fillStyle = shade;
  ctx.fillRect(0, 0, SIZE, SIZE);

  ctx.restore();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}
