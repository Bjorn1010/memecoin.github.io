// Visionneuse 3D de la fiche produit. Chargée à la demande : si Three.js ne
// peut pas être téléchargé ou si WebGL manque, la fiche garde son rendu 2D.

import * as THREE from 'three';
import { createJerseyMesh } from './onze-jersey.js';

export const mountProductViewer = (viewer, product, { flocage, lowPower }) => {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.domElement.setAttribute('role', 'img');
  renderer.domElement.setAttribute(
    'aria-label',
    `Aperçu 3D du maillot ${product.name1} ${product.name2}, glissez pour le faire tourner`,
  );

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 0, 6.1);

  // Éclairage studio : une dominante, un déboucheur doux, un contre-jour
  // teinté. Volontairement contenu — un maillot noir doit rester noir.
  const key = new THREE.SpotLight(0xffffff, 26, 22, Math.PI / 5, 0.85, 1.1);
  key.position.set(2.6, 3.4, 4.2);
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xffffff, 0.55);
  fill.position.set(-3, -1, 2.5);
  scene.add(fill);

  const rim = new THREE.SpotLight(new THREE.Color(product.tasteSecondary), 14, 18, Math.PI / 4, 0.9, 1.2);
  rim.position.set(-2.4, 1.6, -3.2);
  scene.add(rim);

  scene.add(new THREE.AmbientLight(0xffffff, 0.16));

  const jersey = createJerseyMesh(product, { lowPower, flocage });
  scene.add(jersey);

  viewer.appendChild(renderer.domElement);

  const resize = () => {
    const size = viewer.clientWidth;
    if (!size) return;
    renderer.setSize(size, size, false);
    camera.aspect = 1;
    camera.updateProjectionMatrix();
  };
  resize();
  window.addEventListener('resize', resize);

  const rotation = { current: 0, target: 0 };
  const tilt = { current: 0, target: 0 };
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let idle = true;

  const touch = () => {
    idle = false;
    viewer.classList.add('is-touched');
  };

  viewer.addEventListener('pointerdown', (event) => {
    dragging = true;
    touch();
    lastX = event.clientX;
    lastY = event.clientY;
    viewer.setPointerCapture?.(event.pointerId);
  });

  viewer.addEventListener('pointermove', (event) => {
    if (!dragging) return;
    rotation.target += (event.clientX - lastX) * 0.011;
    tilt.target = THREE.MathUtils.clamp(tilt.target + (event.clientY - lastY) * 0.006, -0.55, 0.55);
    lastX = event.clientX;
    lastY = event.clientY;
  });

  const pointerUp = () => {
    dragging = false;
  };
  window.addEventListener('pointerup', pointerUp);
  viewer.addEventListener('pointercancel', pointerUp);

  const clock = new THREE.Clock();
  const animate = () => {
    requestAnimationFrame(animate);
    const delta = Math.min(clock.getDelta(), 0.05);
    if (idle && !dragging) rotation.target += delta * 0.35;

    rotation.current += (rotation.target - rotation.current) * Math.min(1, delta * 6);
    tilt.current += (tilt.target - tilt.current) * Math.min(1, delta * 6);

    jersey.rotation.y = rotation.current;
    jersey.rotation.x = tilt.current;
    jersey.position.y = Math.sin(clock.elapsedTime * 0.9) * 0.045;
    jersey.rotation.z = Math.sin(clock.elapsedTime * 0.6) * 0.03;

    renderer.render(scene, camera);
  };
  animate();

  const showFace = (face) => {
    touch();
    const turns = Math.round(rotation.target / (Math.PI * 2));
    rotation.target = turns * Math.PI * 2 + (face === 'back' ? Math.PI : 0);
    tilt.target = 0;
  };

  return {
    setFlocage: (next) => jersey.userData.setFlocage(next),
    showFace,
  };
};
