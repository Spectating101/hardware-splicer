"use client";

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls, Environment, GizmoHelper, GizmoViewport, Line } from "@react-three/drei";
import * as THREE from "three";

// --- CONSTANTS ---
const COLORS = {
  bg: "#050505", // True Black for AR feel
  solderMask: "#0f2e1b", 
  pads: "#eab308",
  body: "#2d2d2d", 
  pin: "#cccccc",
  selection: "#007fd4",
  alert: "#ef4444",
  ghost: "#00ff00",
};

// --- SPATIAL COMPONENTS ---

function SpatialCallout({ position, label, color = COLORS.selection }: any) {
  // Draws a "Leader Line" from the 3D point to a floating label
  // This gives the "Tuurny/AR" feel
  return (
    <group position={position}>
      {/* The Anchor Point */}
      <mesh>
        <sphereGeometry args={[0.5]} />
        <meshBasicMaterial color={color} />
      </mesh>
      
      {/* The Line (Vertical Rise) */}
      <Line points={[[0, 0, 0], [0, 10, 0]]} color={color} lineWidth={1} />
      
      {/* The Label (Floating at top of line) */}
      <Html position={[0, 10, 0]} center>
        <div 
          className="px-2 py-1 rounded backdrop-blur-md border text-[10px] font-bold whitespace-nowrap shadow-xl"
          style={{ 
            borderColor: color, 
            backgroundColor: `${color}20`, 
            color: '#fff',
            textShadow: '0 1px 2px black'
          }}
        >
          {label}
        </div>
      </Html>
    </group>
  );
}

function ChipMesh({ fp, selected, isGhost = false, onContextMenu }: any) {
  const [w, d] = [8, 8]; 
  const materialProps = isGhost ? { 
    color: COLORS.ghost, wireframe: true, transparent: true, opacity: 0.5 
  } : { 
    color: COLORS.body, roughness: 0.7, metalness: 0.1 
  };

  return (
    <group position={[fp.at.x, 0, fp.at.y]} rotation={[0, THREE.MathUtils.degToRad(fp.at.rot_deg || 0), 0]}>
      {/* Context Menu Trigger (Invisible Hitbox) */}
      <mesh 
        position={[0, 2, 0]} 
        visible={false} 
        onPointerDown={(e) => {
          if (e.button === 2) onContextMenu(e); // Right click
        }}
      >
         <boxGeometry args={[w, 4, d]} />
      </mesh>

      {/* Body */}
      <mesh position={[0, 0.5, 0]}>
        <boxGeometry args={[w, 1, d]} />
        <meshStandardMaterial {...materialProps} />
      </mesh>
      
      {/* Pins */}
      {!isGhost && (
        <>
          <mesh position={[0, 0.1, d/2 + 0.5]}><boxGeometry args={[w - 1, 0.2, 1]} /><meshStandardMaterial color={COLORS.pin} metalness={0.8} /></mesh>
          <mesh position={[0, 0.1, -d/2 - 0.5]}><boxGeometry args={[w - 1, 0.2, 1]} /><meshStandardMaterial color={COLORS.pin} metalness={0.8} /></mesh>
        </>
      )}

      {/* Selection Halo */}
      {selected && (
        <mesh position={[0, 0.1, 0]} rotation={[-Math.PI/2, 0, 0]}>
          <ringGeometry args={[w/1.5, w/1.2, 32]} />
          <meshBasicMaterial color={COLORS.selection} transparent opacity={0.5} />
        </mesh>
      )}

      {/* AR Callout when selected */}
      {selected && (
        <SpatialCallout position={[0, 0, 0]} label={fp.ref} />
      )}
    </group>
  );
}

function BoardScene({ geometry, selection, optimizedGeometry }: any) {
  return (
    <group>
      <mesh position={[40, -0.2, 30]} receiveShadow>
        <boxGeometry args={[84, 0.4, 64]} />
        <meshStandardMaterial color={COLORS.solderMask} roughness={0.3} metalness={0.0} />
      </mesh>

      {/* Dark Grid for "Scanner" feel */}
      <gridHelper args={[200, 40, "#222", "#111"]} position={[40, -0.41, 30]} />

      {geometry?.footprints.map((fp: any) => (
        <ChipMesh 
          key={fp.ref} 
          fp={fp} 
          selected={selection.footprintRef === fp.ref} 
        />
      ))}

      {optimizedGeometry && optimizedGeometry.footprints.map((fp: any) => (
        <ChipMesh 
          key={`ghost-${fp.ref}`} 
          fp={fp} 
          selected={false} 
          isGhost={true}
        />
      ))}

      {/* Cinematic Lighting */}
      <ambientLight intensity={0.2} />
      <pointLight position={[10, 20, 10]} intensity={1} color="#007fd4" distance={50} />
      <pointLight position={[70, 20, 50]} intensity={1} color="#d65d0e" distance={50} />
      <Environment preset="city" />
    </group>
  );
}

export function PcbViewport(props: any) {
  return (
    <div className="h-full w-full bg-[#050505] relative overflow-hidden">
      {/* Background Gradient for "Deep Space" feel */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#050505] to-[#0a0a10] pointer-events-none" />
      
      <Canvas camera={{ position: [40, 80, 60], fov: 40 }} gl={{ antialias: true }}>
        <BoardScene {...props} />
        <OrbitControls makeDefault minPolarAngle={0} maxPolarAngle={Math.PI / 2.1} />
        <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
          <GizmoViewport axisColors={['#9d4b4b', '#2f7f4f', '#3b5b9d']} labelColor="white" />
        </GizmoHelper>
      </Canvas>
    </div>
  );
}
