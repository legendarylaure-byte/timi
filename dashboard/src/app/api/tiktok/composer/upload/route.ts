import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { getAdminFirestore } from '@/lib/firebase-admin';

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

/**
 * Accepts a file upload, stores the original on R2, and creates a stub
 * Firestore `videos` record so the composer can intent-publish it.
 */
export async function POST(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  try {
    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    const title = (formData.get('title') as string) || file?.name || 'Uploaded video';
    const format = (formData.get('format') as string) || 'shorts';

    if (!file) {
      return NextResponse.json({ success: false, error: 'No file uploaded' }, { status: 400 });
    }

    const buffer = Buffer.from(await file.arrayBuffer());
    const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
    const videoId = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const r2Key = `videos/${videoId}-${safeName}`;

    const client = getR2Client();
    await client.send(new PutObjectCommand({
      Bucket: R2_BUCKET,
      Key: r2Key,
      Body: buffer,
      ContentType: file.type || 'video/mp4',
    }));

    const db = getAdminFirestore();
    await db.collection('videos').doc(videoId).set({
      video_id: videoId,
      title: title.replace(/\.[^.]+$/, ''),
      format,
      status: 'uploaded',
      r2_key: r2Key,
      source: 'reviewer_upload',
      duration: undefined,
      created_at: new Date(),
    });

    return NextResponse.json({ success: true, video_id: videoId, r2_key: r2Key });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
