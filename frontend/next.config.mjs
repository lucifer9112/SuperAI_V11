/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // Desktop/CI sandboxes can reject Next's child build workers with EPERM.
    workerThreads: true,
    webpackBuildWorker: false,
  },
};

export default nextConfig;
