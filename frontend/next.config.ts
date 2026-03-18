import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "https://localhost:3017/api/:path*",
      },
      {
        source: "/ws/:path*",
        destination: "https://localhost:3017/ws/:path*",
      },
    ];
  },
};

export default nextConfig;
