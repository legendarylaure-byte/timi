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

export async function POST(request: Request) {
  try {
    const { ids } = await request.json();
    if (!Array.isArray(ids) || ids.length === 0) {
      return NextResponse.json({ success: false, error: 'No video IDs provided' }, { status: 400 });
    }

    const db = getAdminFirestore();
    const batch = db.batch();
    const results: { id: string; r2_deleted: boolean; firestore_deleted: boolean; error?: string }[] = [];

    for (const id of ids) {
      try {
        const docRef = db.collection('videos').doc(id);
        const snap = await docRef.get();
        let r2_deleted = false;

        if (snap.exists) {
          const data = snap.data();
          const r2Key = data?.r2_key as string | undefined;
          if (r2Key) {
            r2_deleted = await deleteFromR2(r2Key);
          }
          const thumbKey = `thumbnails/${id}.jpg`;
          await deleteFromR2(thumbKey);
          batch.delete(docRef);
        }

        results.push({ id, r2_deleted, firestore_deleted: snap.exists });
      } catch (err: any) {
        results.push({ id, r2_deleted: false, firestore_deleted: false, error: err.message });
      }
    }

    await batch.commit();

    const deleted = results.filter(r => r.firestore_deleted).length;
    const failed = results.filter(r => r.error).length;

    return NextResponse.json({ success: true, deleted, failed, results });
  } catch (error: any) {
    console.error('[BATCH DELETE] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
