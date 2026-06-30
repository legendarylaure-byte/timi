import { NextResponse } from 'next/server';
import { S3Client, ListObjectsV2Command } from '@aws-sdk/client-s3';

const R2_ACCOUNT_ID = process.env.CLOUDFLARE_ACCOUNT_ID || '';
const R2_ACCESS_KEY = process.env.CLOUDFLARE_R2_ACCESS_KEY_ID || '';
const R2_SECRET_KEY = process.env.CLOUDFLARE_R2_SECRET_ACCESS_KEY || '';
const R2_BUCKET = process.env.CLOUDFLARE_R2_BUCKET || 'vyom-ai-videos';

function getR2Client(): S3Client {
  return new S3Client({
    region: 'auto',
    endpoint: `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
    credentials: {
      accessKeyId: R2_ACCESS_KEY,
      secretAccessKey: R2_SECRET_KEY,
    },
  });
}

export async function GET() {
  try {
    if (!R2_ACCOUNT_ID || !R2_ACCESS_KEY || !R2_SECRET_KEY) {
      return NextResponse.json({
        connected: false,
        configured: false,
        error: 'R2 credentials not configured',
      });
    }

    const client = getR2Client();
    const command = new ListObjectsV2Command({
      Bucket: R2_BUCKET,
    });

    const response = await client.send(command);

    const keyCount = response.KeyCount || 0;
    let totalBytes = 0;
    if (response.Contents) {
      totalBytes = response.Contents.reduce(
        (sum, obj) => sum + (obj.Size || 0),
        0
      );
    }
    const deleteMarkerCount = 0;

    const totalSizeMB = Math.round((totalBytes / (1024 * 1024)) * 10) / 10;
    const totalSizeGB = Math.round((totalSizeMB / 1024) * 100) / 100;
    const freeGB = Math.max(0, 10 - totalSizeGB);

    return NextResponse.json({
      connected: true,
      configured: true,
      bucket: R2_BUCKET,
      objects: keyCount,
      total_size_bytes: totalBytes,
      total_size_mb: totalSizeMB,
      total_size_gb: totalSizeGB,
      free_gb: freeGB,
      free_percent: Math.round((freeGB / 10) * 100),
      pending_deletion: deleteMarkerCount,
      limit_gb: 10,
    });
  } catch (error: any) {
    return NextResponse.json({
      connected: false,
      configured: true,
      error: error.message,
    });
  }
}
