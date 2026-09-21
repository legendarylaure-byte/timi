import { NextResponse } from 'next/server';
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

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

export async function GET(request: Request) {
  try {
    if (!R2_ACCOUNT_ID || !R2_ACCESS_KEY || !R2_SECRET_KEY) {
      return NextResponse.json({ success: false, error: 'R2 credentials not configured' }, { status: 500 });
    }
    const { searchParams } = new URL(request.url);
    const key = (searchParams.get('key') || '').trim();
    if (!key) {
      return NextResponse.json({ success: false, error: 'Missing key param' }, { status: 400 });
    }
    const client = getR2Client();
    const url = await getSignedUrl(client, new GetObjectCommand({ Bucket: R2_BUCKET, Key: key }), { expiresIn: 3600 });
    return NextResponse.json({ success: true, url });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}