import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  eslint: {
    ignoreDuringBuilds: true,
  },
  env: {
    CIRCUIT_AI_API_URL: process.env.CIRCUIT_AI_API_URL ?? 'http://localhost:5000',
    CIRCUIT_AI_VISION_URL: process.env.CIRCUIT_AI_VISION_URL ?? 'http://localhost:8000',
    MECHA_API_URL: process.env.MECHA_API_URL ?? 'http://localhost:8085',
  },
};

export default nextConfig;
