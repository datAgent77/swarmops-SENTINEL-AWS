import { dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the workspace root to this app so a stray lockfile elsewhere (e.g. in
  // the home directory) can't make Next infer the wrong root and break module
  // resolution (@xyflow/react) or emit the "multiple lockfiles" warning.
  turbopack: { root: __dirname },
};

export default nextConfig;
