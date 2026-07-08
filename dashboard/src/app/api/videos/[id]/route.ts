import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { S3Client, DeleteObjectCommand } from '@aws-sdk/client-s3';

const R2_ACCOUNT_ID = process.env.CLOUDFLARE_ACCOUNT_ID || '';
const R2_ACCESS_KEY = process.env.CLOUDFLARE_R2_ACCESS_KEY_ID || '';
const R2_SECRET_KEY = process.env.CLOUDFLARE_R2_SECRET_ACCESS_KEY || '';
const R2_BUCKET = process.env.CLOUDFLARE_R2_BUCKET || 'vyom-ai-videos';

function getR2Client(): S3Client {
  return new S3Client({
    region: 'auto',
    endpoint: `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
    credentials: { accessKeyId: R2_ACCESS_KEY, secretAccessKey: R2_SECRET_KEY },
  });
}

async function deleteFromR2(key: string): Promise<boolean> {
  try {
    if (!R2_ACCOUNT_ID || !R2_ACCESS_KEY || !R2_SECRET_KEY) return false;
    const client = getR2Client();
    await client.send(new DeleteObjectCommand({ Bucket: R2_BUCKET, Key: key }));
    return true;
  } catch {
    return false;
  }
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const db = getAdminFirestore();
    const docRef = db.collection('videos').doc(id);
    const snap = await docRef.get();

    if (!snap.exists) {
      return NextResponse.json({ success: false, error: 'Video not found' }, { status: 404 });
    }

    const data = snap.data();
    const r2Key = data?.r2_key as string | undefined;
    const format = data?.format as string | undefined;

    const deletedKeys: string[] = [];
    const failedKeys: string[] = [];

    if (r2Key) {
      const ok = await deleteFromR2(r2Key);
      if (ok) deletedKeys.push(r2Key);
      else failedKeys.push(r2Key);
    }

    const thumbnailKey = `thumbnails/${id}.jpg`;
    await deleteFromR2(thumbnailKey);

    await docRef.delete();

    return NextResponse.json({
      success: true,
      deleted_keys: deletedKeys,
      failed_keys: failedKeys,
    });
  } catch (error: any) {
    console.error('[DELETE VIDEO] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
