import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The shared API client ships TypeScript source (packages/api-client).
  transpilePackages: ["@karenbot/api-client"],
};

export default nextConfig;
