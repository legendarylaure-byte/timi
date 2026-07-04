// @ts-check
import path from 'path';
import TsconfigPathsPlugin from 'tsconfig-paths-webpack-plugin';

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
    config.resolve.plugins = [
      ...(config.resolve.plugins || []),
      new TsconfigPathsPlugin({
        configFile: path.resolve(process.cwd(), 'tsconfig.json'),
        baseUrl: path.resolve(process.cwd()),
      }),
    ];
    config.resolve.alias['@'] = path.resolve(process.cwd(), 'src');
    return config;
  },

};

export default nextConfig;
