import { withSentryConfig } from '@sentry/nextjs';
import path from 'path';

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ['firebasestorage.googleapis.com'],
  },
  env: {
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME || 'Vyom Ai Cloud',
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
  },
  webpack: (config) => {
    config.resolve.alias['@'] = path.resolve(import.meta.dirname, 'src');
    return config;
  },

};

const sentryConfig = {
  org: process.env.SENTRY_ORG || '',
  project: process.env.SENTRY_PROJECT || '',
  authToken: process.env.SENTRY_AUTH_TOKEN || '',
  telemetry: false,
  hideSourceMaps: true,
  disableLogger: true,
  autoInstrumentServerFunctions: false,
  sourcemaps: {
    disable: true,
  },
};

export default withSentryConfig(nextConfig, sentryConfig);
