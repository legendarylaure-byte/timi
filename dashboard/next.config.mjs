// @ts-check
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Log to confirm this file is loaded during build
console.log('[CONFIG] next.config.mjs LOADED, __dirname:', __dirname, 'cwd:', process.cwd());

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
    const srcDir = path.resolve(process.cwd(), 'src');
    console.log('[WEBPACK] cwd:', process.cwd(), 'alias @ =>', srcDir, 'isServer:', isServer);
    config.resolve.alias['@'] = srcDir;
    return config;
  },

};

export default nextConfig;
