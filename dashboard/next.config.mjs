// @ts-check
import path from 'path';
import fs from 'fs';

const srcDir = path.resolve(process.cwd(), 'src');

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ['firebasestorage.googleapis.com'],
  },
  env: {
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME || 'Vyom Ai Cloud',
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
  },
  webpack: (config, { isServer }) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': srcDir,
    };
    config.resolve.modules = [srcDir, ...(config.resolve.modules || [])];
    // Verify the alias resolves
    const testFile = path.join(srcDir, 'components/pipeline/ActivePipeline.tsx');
    console.log(`[WEBPACK] srcDir=${srcDir} exists=${fs.existsSync(srcDir)} testFile=${fs.existsSync(testFile)}`);
    return config;
  },

};

export default nextConfig;
