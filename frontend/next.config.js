/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  experimental: {
    // Some desktop/CI sandboxes reject child build workers with EPERM.
    workerThreads: true,
    webpackBuildWorker: false,
  },
};

module.exports = nextConfig;
