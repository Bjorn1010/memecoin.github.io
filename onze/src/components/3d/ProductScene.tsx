"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Colorway } from "@/lib/types";
import { createJerseyTexture } from "@/components/3d/jerseyTexture";

/* The 360° product viewer. Unlike the hero — which the pointer only nudges —
 * this one hands full orbit and zoom to the user, because on a product page
 * inspecting the garment IS the task. */

function Garment({
  colorway,
  monogram,
  number,
  playerName,
}: {
  colorway: Colorway;
  monogram: string;
  number: string;
  playerName?: string;
}) {
  const group = useRef<THREE.Group>(null);
  const light = useRef<THREE.PointLight>(null);

  /* Front and back are separate textures on separate faces, so orbiting past
     90° reveals the actual flocage rather than a mirrored front. */
  const front = useMemo(
    () => createJerseyTexture(colorway, monogram, number, "front"),
    [colorway, monogram, number],
  );
  const back = useMemo(
    () => createJerseyTexture(colorway, monogram, number, "back", playerName),
    [colorway, monogram, number, playerName],
  );

  const geometry = useMemo(() => {
    const geo = new THREE.PlaneGeometry(3.0, 3.25, 40, 52);
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      pos.setZ(i, Math.cos(x * 1.5) * 0.2 + Math.sin(x * 3.2 + y * 0.5) * 0.05);
    }
    geo.computeVertexNormals();
    return geo;
  }, []);

  useEffect(
    () => () => {
      geometry.dispose();
      front?.dispose();
      back?.dispose();
    },
    [geometry, front, back],
  );

  /* Key light orbits slowly to keep the fabric alive while the user inspects. */
  useFrame((state) => {
    if (light.current) {
      light.current.position.x = Math.sin(state.clock.elapsedTime * 0.4) * 3.5;
      light.current.position.z = 3 + Math.cos(state.clock.elapsedTime * 0.4) * 1.5;
    }
  });

  return (
    <group ref={group}>
      <mesh geometry={geometry}>
        <meshPhysicalMaterial
          map={front ?? undefined}
          transparent
          alphaTest={0.5}
          side={THREE.FrontSide}
          roughness={0.72}
          metalness={0.05}
          sheen={0.7}
          sheenRoughness={0.6}
          sheenColor="#ffffff"
        />
      </mesh>
      {/* Back face, flipped and offset a hair so the two never z-fight. */}
      <mesh geometry={geometry} rotation={[0, Math.PI, 0]} position={[0, 0, -0.02]}>
        <meshPhysicalMaterial
          map={back ?? undefined}
          transparent
          alphaTest={0.5}
          side={THREE.FrontSide}
          roughness={0.72}
          metalness={0.05}
          sheen={0.7}
          sheenRoughness={0.6}
          sheenColor="#ffffff"
        />
      </mesh>
      <pointLight ref={light} intensity={40} distance={16} />
    </group>
  );
}

export default function ProductScene({
  colorway,
  monogram,
  number,
  playerName,
}: {
  colorway: Colorway;
  monogram: string;
  number: string;
  playerName?: string;
}) {
  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 0, 5.6], fov: 42 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
    >
      <ambientLight intensity={0.6} />
      <directionalLight position={[-4, 5, 4]} intensity={1.5} color="#dfe6ff" />
      <directionalLight position={[3, -2, -4]} intensity={1.8} color="#0a9c4a" />
      <Garment colorway={colorway} monogram={monogram} number={number} playerName={playerName} />
      {/* Vertical orbit is clamped: letting the user tumble the garment upside
          down looks broken, not flexible. */}
      <OrbitControls
        enablePan={false}
        minDistance={4}
        maxDistance={8}
        minPolarAngle={Math.PI / 3}
        maxPolarAngle={(Math.PI * 2) / 3}
        autoRotate
        autoRotateSpeed={0.8}
        makeDefault
      />
    </Canvas>
  );
}
