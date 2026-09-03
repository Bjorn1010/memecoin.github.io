"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Team } from "@/lib/types";
import { createJerseyTexture } from "@/components/3d/jerseyTexture";
import { crowdTexture, pitchTexture, playerTexture } from "@/components/3d/stadium";

/* The hero: three kits on a slow carousel, in a stadium at night.
 *
 * Everything — kits, turf, crowd, players — is painted to canvases at runtime.
 * No model files, no photography, no club marks: the scene downloads nothing
 * beyond the code itself, which is also why it can ship in a storefront that
 * sells unofficial replicas. */

const DRAPE = (geo: THREE.PlaneGeometry) => {
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    const y = pos.getY(i);
    pos.setZ(i, Math.cos(x * 1.5) * 0.2 + Math.sin(x * 3.2 + y * 0.5) * 0.05);
  }
  geo.computeVertexNormals();
  return geo;
};

function Kit({
  team,
  index,
  count,
}: {
  team: Team;
  index: number;
  count: number;
}) {
  const group = useRef<THREE.Group>(null);

  const texture = useMemo(
    () => createJerseyTexture(team.colorway, team.monogram, `${index + 9}`),
    [team, index],
  );
  const geometry = useMemo(() => DRAPE(new THREE.PlaneGeometry(2.5, 2.7, 32, 40)), []);

  useEffect(
    () => () => {
      geometry.dispose();
      texture?.dispose();
    },
    [geometry, texture],
  );

  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.elapsedTime;
    /* Each kit sits at its own station on a slowly turning carousel. The
       offset per index is what keeps them evenly spaced as the ring rotates. */
    const angle = (index / count) * Math.PI * 2 + t * 0.18;
    const radius = 2.3;
    group.current.position.x = Math.sin(angle) * radius;
    group.current.position.z = Math.cos(angle) * radius - 1.5;
    /* Billboarded, never turned with the ring: rotating a double-sided plane
       past 90° shows its back, and the crest reads mirrored. A small sway
       keeps it from looking like a sticker. */
    group.current.rotation.y = Math.sin(angle) * 0.16;
    group.current.position.y = 0.1 + Math.sin(t * 0.7 + index * 2.1) * 0.08;
    /* Kits at the back of the ring shrink, which reads as depth without
       needing fog to do the work. */
    const depth = (Math.cos(angle) + 1) / 2;
    group.current.scale.setScalar(0.46 + depth * 0.18);
  });

  return (
    <group ref={group}>
      <mesh geometry={geometry}>
        <meshPhysicalMaterial
          map={texture ?? undefined}
          transparent
          alphaTest={0.5}
          side={THREE.DoubleSide}
          roughness={0.74}
          metalness={0.05}
          sheen={0.6}
          sheenRoughness={0.6}
          sheenColor="#ffffff"
        />
      </mesh>
    </group>
  );
}

function Stadium() {
  const pitch = useMemo(() => pitchTexture(), []);
  const crowd = useMemo(() => crowdTexture(), []);
  const players = useMemo(
    () => [0, 1, 2].map((p) => playerTexture(p as 0 | 1 | 2)),
    [],
  );

  useEffect(
    () => () => {
      pitch?.dispose();
      crowd?.dispose();
      players.forEach((p) => p?.dispose());
    },
    [pitch, crowd, players],
  );

  /* Figures scattered across the middle distance. Positions are fixed rather
     than random so the composition is the same on every load. */
  const figures = [
    { x: -7.4, z: -9, s: 1.35, p: 0 },
    { x: -3.2, z: -13, s: 1.05, p: 1 },
    { x: 1.6, z: -11, s: 1.15, p: 2 },
    { x: 6.8, z: -8.5, s: 1.4, p: 1 },
    { x: 10.5, z: -14, s: 0.95, p: 0 },
    { x: -11.2, z: -12.5, s: 1.0, p: 2 },
  ];

  return (
    <group>
      {/* Turf, laid flat and running to the horizon. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2.6, -5]} receiveShadow>
        <planeGeometry args={[76, 32]} />
        <meshStandardMaterial map={pitch ?? undefined} roughness={1} />
      </mesh>

      {/* The stand. A plain wall at a known depth — a cylinder arc kept
          wrapping round in front of the camera. */}
      <mesh position={[0, 2.2, -21]}>
        <planeGeometry args={[76, 15]} />
        <meshBasicMaterial map={crowd ?? undefined} toneMapped={false} />
      </mesh>

      {/* Players, as billboards so they always face the camera. */}
      {figures.map((f, i) => (
        <sprite key={i} position={[f.x, -2.6 + f.s * 0.9, f.z]} scale={[f.s * 0.55, f.s * 1.1, 1]}>
          <spriteMaterial
            map={players[f.p] ?? undefined}
            transparent
            opacity={0.72}
            depthWrite={false}
          />
        </sprite>
      ))}
    </group>
  );
}

function Rig() {
  const { camera } = useThree();
  /* Pointer parallax on the camera rather than the kits: moving the viewpoint
     shifts the whole stadium together, which is what sells the depth. */
  useFrame((state, delta) => {
    const px = state.pointer.x * 0.9;
    const py = state.pointer.y * 0.4;
    camera.position.x = THREE.MathUtils.damp(camera.position.x, px, 2.2, delta);
    camera.position.y = THREE.MathUtils.damp(camera.position.y, 0.4 + py, 2.2, delta);
    camera.lookAt(0, 0.1, -1);
  });
  return null;
}

export default function StadiumScene({ teams }: { teams: Team[] }) {
  const cast = teams.slice(0, 3);

  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 0.4, 7.4], fov: 44 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ pointerEvents: "none" }}
    >
      {/* Night match: a cool ambient base, warm floodlights from above, and a
          low fill so the kits do not go black at the bottom. */}
      <ambientLight intensity={0.75} color="#cfe6ff" />
      <directionalLight position={[-6, 9, 5]} intensity={1.5} color="#ffffff" />
      <directionalLight position={[7, 6, -3]} intensity={1.1} color="#ffe9a8" />
      <pointLight position={[0, -3, 4]} intensity={12} distance={16} color="#bfe6cd" />

      <Stadium />
      {/* Offset right: the copy owns the left half of the hero, and a kit
          drifting across the headline is worse than no kit at all. */}
      <group position={[2.9, 0.25, 0]}>
        {cast.map((team, i) => (
          <Kit key={team.slug} team={team} index={i} count={cast.length} />
        ))}
      </group>
      <Rig />
    </Canvas>
  );
}
