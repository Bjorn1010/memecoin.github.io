import * as THREE from "three";

/* Procedural stadium dressing for the hero: the pitch, the crowd, and the
 * players on it. All painted to canvases at runtime, so the scene still ships
 * zero image bytes and cannot fall foul of anyone's photography rights.
 *
 * The silhouettes are generic figures, deliberately not any real player. */

/** Mown turf, painted in perspective-friendly bands with a worn centre. */
export function pitchTexture() {
  const W = 512, H = 512;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const x = c.getContext("2d");
  if (!x) return null;

  x.fillStyle = "#0a8f43";
  x.fillRect(0, 0, W, H);

  /* Alternating cut bands — the single most recognisable pitch cue. */
  const band = H / 10;
  x.fillStyle = "#0b9c49";
  for (let y = 0; y < H; y += band * 2) x.fillRect(0, y, W, band);

  /* Painted markings: halfway line and centre circle. */
  x.strokeStyle = "rgba(255,255,255,0.55)";
  x.lineWidth = 3;
  x.beginPath();
  x.moveTo(0, H / 2);
  x.lineTo(W, H / 2);
  x.stroke();
  x.beginPath();
  x.arc(W / 2, H / 2, W * 0.13, 0, Math.PI * 2);
  x.stroke();

  /* Wear: without a little noise the grass reads as flat green plastic. */
  x.globalAlpha = 0.05;
  for (let i = 0; i < 900; i++) {
    x.fillStyle = Math.random() > 0.5 ? "#ffffff" : "#000000";
    const r = Math.random() * 3;
    x.fillRect(Math.random() * W, Math.random() * H, r, r);
  }
  x.globalAlpha = 1;

  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(3, 3);
  return t;
}

/** A packed stand: tiers of small warm dots over a dark ground. */
export function crowdTexture() {
  const W = 1024, H = 256;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const x = c.getContext("2d");
  if (!x) return null;

  const sky = x.createLinearGradient(0, 0, 0, H);
  sky.addColorStop(0, "#04140b");
  sky.addColorStop(1, "#0a2a17");
  x.fillStyle = sky;
  x.fillRect(0, 0, W, H);

  /* Rows of spectators, thinning toward the top of the stand. */
  for (let row = 0; row < 26; row++) {
    const y = H * 0.18 + row * (H * 0.031);
    const density = 1 - row / 34;
    for (let i = 0; i < 260 * density; i++) {
      const hue = 30 + Math.random() * 40;
      const light = 30 + Math.random() * 45;
      x.fillStyle = `hsl(${hue} 35% ${light}% / ${0.5 + Math.random() * 0.5})`;
      x.beginPath();
      x.arc(Math.random() * W, y + (Math.random() - 0.5) * 4, 1.6, 0, Math.PI * 2);
      x.fill();
    }
  }

  /* Stand roof line, so the crowd reads as enclosed rather than as static. */
  x.fillStyle = "#020a05";
  x.fillRect(0, 0, W, H * 0.16);

  const t = new THREE.CanvasTexture(c);
  t.wrapS = THREE.RepeatWrapping;
  t.repeat.set(2, 1);
  return t;
}

/** One generic player silhouette, drawn as a flat figure for a billboard. */
export function playerTexture(pose: 0 | 1 | 2) {
  const W = 128, H = 256;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const x = c.getContext("2d");
  if (!x) return null;

  x.fillStyle = "#04170c";
  const cx = W / 2;

  /* head */
  x.beginPath();
  x.arc(cx, H * 0.13, W * 0.1, 0, Math.PI * 2);
  x.fill();

  /* torso */
  x.beginPath();
  x.moveTo(cx - W * 0.15, H * 0.22);
  x.lineTo(cx + W * 0.15, H * 0.22);
  x.lineTo(cx + W * 0.12, H * 0.55);
  x.lineTo(cx - W * 0.12, H * 0.55);
  x.closePath();
  x.fill();

  /* arms and legs vary per pose so a row of figures does not read as clones */
  const armSpread = [0.3, 0.42, 0.24][pose];
  const stride = [0.1, 0.2, 0.04][pose];
  x.lineWidth = W * 0.075;
  x.strokeStyle = "#04170c";
  x.lineCap = "round";

  x.beginPath();
  x.moveTo(cx - W * 0.13, H * 0.26);
  x.lineTo(cx - W * armSpread, H * 0.44);
  x.moveTo(cx + W * 0.13, H * 0.26);
  x.lineTo(cx + W * (armSpread * 0.8), H * 0.4);
  x.stroke();

  x.lineWidth = W * 0.095;
  x.beginPath();
  x.moveTo(cx - W * 0.06, H * 0.55);
  x.lineTo(cx - W * (0.08 + stride), H * 0.93);
  x.moveTo(cx + W * 0.06, H * 0.55);
  x.lineTo(cx + W * (0.08 + stride * 0.5), H * 0.93);
  x.stroke();

  const t = new THREE.CanvasTexture(c);
  return t;
}
