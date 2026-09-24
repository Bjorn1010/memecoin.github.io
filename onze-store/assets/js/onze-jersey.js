// Géométrie et matériaux 3D du maillot Onze.
// Les textures viennent de onze-jersey-texture.js (canvas 2D, sans Three.js),
// partagées avec les vignettes de la boutique.

import * as THREE from 'three';
import { createJerseyTextures, SILHOUETTE_PATH } from './onze-jersey-texture.js';

export const JERSEY_WIDTH = 1.8;
export const JERSEY_HEIGHT = 2.4;

const bounds = {
  minX: -JERSEY_WIDTH / 2,
  maxX: JERSEY_WIDTH / 2,
  minY: -JERSEY_HEIGHT / 2,
  maxY: JERSEY_HEIGHT / 2,
};

// Coordonnées normalisées (u, v) -> repère 3D centré.
const toX = (u) => (u - 0.5) * JERSEY_WIDTH;
const toY = (v) => (0.5 - v) * JERSEY_HEIGHT;

/** Silhouette 3D dérivée du tracé partagé avec les vignettes 2D. */
export const buildJerseyShape = () => {
  const shape = new THREE.Shape();
  SILHOUETTE_PATH.forEach((segment) => {
    if (segment.type === 'M') shape.moveTo(toX(segment.u), toY(segment.v));
    else if (segment.type === 'L') shape.lineTo(toX(segment.u), toY(segment.v));
    else shape.quadraticCurveTo(toX(segment.cu), toY(segment.cv), toX(segment.u), toY(segment.v));
  });
  shape.closePath();
  return shape;
};

const uvAt = (vertices, i) =>
  new THREE.Vector2(
    (vertices[i * 3] - bounds.minX) / JERSEY_WIDTH,
    (vertices[i * 3 + 1] - bounds.minY) / JERSEY_HEIGHT,
  );

const UVGenerator = {
  generateTopUV: (geometry, vertices, a, b, c) => [uvAt(vertices, a), uvAt(vertices, b), uvAt(vertices, c)],
  generateSideWallUV: (geometry, vertices, a, b, c, d) => [
    uvAt(vertices, a),
    uvAt(vertices, b),
    uvAt(vertices, c),
    uvAt(vertices, d),
  ],
};

// Répartit les triangles en 3 matériaux : 0 = avant (+Z), 1 = arrière (-Z),
// 2 = tranches. Le verso porte le flocage, il lui faut sa propre texture.
const splitFacesByNormal = (geometry) => {
  const normal = geometry.getAttribute('normal');
  const triangleCount = normal.count / 3;
  const classify = (tri) => {
    let nz = 0;
    for (let v = 0; v < 3; v++) nz += normal.getZ(tri * 3 + v);
    nz /= 3;
    if (nz > 0.7) return 0;
    if (nz < -0.7) return 1;
    return 2;
  };

  geometry.clearGroups();
  let runStart = 0;
  let runMaterial = classify(0);
  for (let tri = 1; tri < triangleCount; tri++) {
    const material = classify(tri);
    if (material !== runMaterial) {
      geometry.addGroup(runStart * 3, (tri - runStart) * 3, runMaterial);
      runStart = tri;
      runMaterial = material;
    }
  }
  geometry.addGroup(runStart * 3, (triangleCount - runStart) * 3, runMaterial);
};

let cachedGeometry = null;

export const buildJerseyGeometry = () => {
  if (cachedGeometry) return cachedGeometry;
  // Tissu : faible épaisseur et biseau doux, sinon le maillot lit comme du carton.
  const geometry = new THREE.ExtrudeGeometry(buildJerseyShape(), {
    depth: 0.07,
    bevelEnabled: true,
    bevelThickness: 0.022,
    bevelSize: 0.018,
    bevelSegments: 3,
    curveSegments: 24,
    UVGenerator,
  });
  geometry.center();
  geometry.computeVertexNormals();
  splitFacesByNormal(geometry);
  cachedGeometry = geometry;
  return geometry;
};

const toTexture = (canvas) => {
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
};

const makeFabricMaterial = (map, lowPower) => {
  const params = { color: 0xffffff, map, metalness: 0.04, roughness: 0.78 };
  if (lowPower) return new THREE.MeshStandardMaterial(params);
  return new THREE.MeshPhysicalMaterial({
    ...params,
    sheen: 1,
    sheenRoughness: 0.4,
    sheenColor: new THREE.Color(0xffffff),
    reflectivity: 0.18,
    ior: 1.4,
    envMapIntensity: 0.55,
  });
};

/**
 * Maillot 3D complet. Le groupe expose `userData.setFlocage()` pour mettre à
 * jour nom et numéro sans reconstruire la géométrie.
 */
export const createJerseyMesh = (design, options = {}) => {
  const { lowPower = false, flocage = {}, onMaterial } = options;
  const textures = createJerseyTextures(design, flocage);

  const frontMaterial = makeFabricMaterial(toTexture(textures.front), lowPower);
  const backMaterial = makeFabricMaterial(toTexture(textures.back), lowPower);
  // La tranche est une couture, pas un liseré fluo : on assombrit la couleur
  // d'accent pour qu'elle ne domine pas le maillot.
  const edgeColor = new THREE.Color(design.secondary).multiplyScalar(0.42);
  const edgeMaterial = lowPower
    ? new THREE.MeshStandardMaterial({ color: edgeColor, roughness: 0.9, metalness: 0.02 })
    : new THREE.MeshPhysicalMaterial({
        color: edgeColor,
        roughness: 0.9,
        metalness: 0.02,
        sheen: 0.5,
        sheenColor: new THREE.Color(0xffffff),
        envMapIntensity: 0.25,
      });

  [frontMaterial, backMaterial, edgeMaterial].forEach((material) => onMaterial?.(material));

  const group = new THREE.Group();
  const mesh = new THREE.Mesh(buildJerseyGeometry(), [frontMaterial, backMaterial, edgeMaterial]);
  mesh.name = 'Shell';
  group.add(mesh);

  group.userData.setFlocage = (next) => {
    const updated = createJerseyTextures(design, next);
    frontMaterial.map?.dispose();
    backMaterial.map?.dispose();
    frontMaterial.map = toTexture(updated.front);
    backMaterial.map = toTexture(updated.back);
    frontMaterial.needsUpdate = true;
    backMaterial.needsUpdate = true;
  };

  return group;
};
