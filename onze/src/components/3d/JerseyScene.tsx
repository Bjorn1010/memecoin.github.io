"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Colorway } from "@/lib/types";
import { createJerseyTexture } from "@/components/3d/jerseyTexture";

/* The hero object. A subdivided plane displaced into a cloth-like drape, lit
 * by a moving key light and steered by the pointer.
 *
 * Why not a GLTF garment: a real jersey model is 2–5 MB before textures, and
 * the brief puts speed above fidelity. This carries no assets at all, renders
 * in one draw call, and still reads as fabric because the displacement and the
 * specular sweep are doing the work a model would.
 */

function ClothJersey({ colorway, monogram }: { colorway: Colorway; monogram: string }) {
  const mesh = useRef<THREE.Mesh>(null);
  const light = useRef<THREE.PointLight>(null);
  const { viewport } = useThree();

  const texture = useMemo(
    () => createJerseyTexture(colorway, monogram, "10"),
    [colorway, monogram],
  );

  /* Bake the drape once. Two crossed sine waves plus a downward falloff give
     the shoulder-to-hem hang; recomputing per frame would cost far more than
     it adds. */
  const geometry = useMemo(() => {
    /* Near-square to match the texture's 240×260 source box — a taller plane
       would stretch the silhouette's shoulders. */
    const geo = new THREE.PlaneGeometry(3.0, 3.25, 48, 64);
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      const drape = Math.cos(x * 1.6) * 0.22;
      const fold = Math.sin(x * 3.4 + y * 0.6) * 0.06;
      const hang = (1 - (y + 1.7) / 3.4) * 0.12;
      pos.setZ(i, drape + fold - hang);
    }
    geo.computeVertexNormals();
    return geo;
  }, []);

  useEffect(() => () => {
    geometry.dispose();
    texture?.dispose();
  }, [geometry, texture]);

  useFrame((state, delta) => {
    if (!mesh.current) return;
    const { pointer, clock } = state;

    /* Pointer steers rotation; the lerp is what turns a twitchy cursor into a
       weighted object. Clamped so the kit never turns edge-on. */
    const targetY = pointer.x * 0.42;
    const targetX = -pointer.y * 0.24;
    mesh.current.rotation.y = THREE.MathUtils.damp(mesh.current.rotation.y, targetY, 3, delta);
    mesh.current.rotation.x = THREE.MathUtils.damp(mesh.current.rotation.x, targetX, 3, delta);

    /* Idle breathing, so the object is alive before the pointer arrives. */
    mesh.current.position.y = Math.sin(clock.elapsedTime * 0.6) * 0.05;

    /* The key light orbits, which is what produces the travelling sheen across
       the fabric — the single most "premium" cue in the scene. */
    if (light.current) {
      light.current.position.x = Math.sin(clock.elapsedTime * 0.45) * 3;
      light.current.position.z = 2.5 + Math.cos(clock.elapsedTime * 0.45) * 1.2;
    }
  });

  const scale = Math.min(1, viewport.width / 5);

  return (
    <Float speed={1.1} rotationIntensity={0.18} floatIntensity={0.35}>
      <mesh ref={mesh} geometry={geometry} scale={scale} castShadow>
        {/* transparent + alphaTest discards everything outside the garment
            outline baked into the texture's alpha channel, so the mesh silhouette
            is a jersey rather than a rectangle. alphaTest (not blending) keeps it
            writing depth, which matters for the double-sided drape. */}
        <meshPhysicalMaterial
          map={texture ?? undefined}
          transparent
          alphaTest={0.5}
          side={THREE.DoubleSide}
          roughness={0.72}
          metalness={0.06}
          clearcoat={0.28}
          clearcoatRoughness={0.5}
          sheen={0.7}
          sheenRoughness={0.6}
          sheenColor="#ffffff"
        />
      </mesh>
      <pointLight ref={light} intensity={38} distance={14} color="#ffffff" />
    </Float>
  );
}

export default function JerseyScene({
  colorway,
  monogram,
}: {
  colorway: Colorway;
  monogram: string;
}) {
  return (
    <Canvas
      /* dpr capped at 1.5: past that the fill cost climbs fast with no visible
         gain on a soft-lit cloth surface. */
      dpr={[1, 1.5]}
      camera={{ position: [0, 0, 5.4], fov: 42 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      /* Only redraw when something changed — the scene idles at 0% GPU when the
         pointer is still and the float has settled. */
      frameloop="always"
      style={{ pointerEvents: "none" }}
    >
      <ambientLight intensity={0.55} />
      <directionalLight position={[-4, 5, 3]} intensity={1.6} color="#dfe6ff" />
      {/* Volt rim from behind, tying the 3D object to the system accent. */}
      <directionalLight position={[3, -2, -4]} intensity={2.2} color="#0a9c4a" />
      {/* Deliberately no drei <Environment>: every preset pulls an HDR from a
          CDN at runtime. Three analytic lights cost nothing and keep the hero
          working offline and behind a strict CSP. */}
      <ClothJersey colorway={colorway} monogram={monogram} />
    </Canvas>
  );
}
