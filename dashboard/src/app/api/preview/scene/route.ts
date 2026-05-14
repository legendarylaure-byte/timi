import { NextResponse } from 'next/server';
import { getAdminAuth } from '@/lib/firebase-admin';
import { spawn } from 'child_process';
import path from 'path';

async function verifyAuth(request: Request): Promise<{ uid: string } | null> {
  const authHeader = request.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) return null;
  try {
    const token = authHeader.slice(7);
    const decoded = await getAdminAuth().verifyIdToken(token);
    return { uid: decoded.uid };
  } catch {
    return null;
  }
}

export async function POST(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const sceneConfig = body.scene;
    const formatType = body.format_type || 'shorts';

    if (!sceneConfig) {
      return NextResponse.json({ success: false, error: 'Missing scene config' }, { status: 400 });
    }

    sceneConfig.format_type = formatType;

    const projectRoot = path.resolve(process.cwd(), '..');
    const pythonPath = process.env.PYTHON_PATH || path.join(projectRoot, 'agents', '.venv', 'bin', 'python');
    const scriptPath = path.join(projectRoot, 'agents', 'utils', 'preview_frame.py');
    const agentsDir = path.join(projectRoot, 'agents');

    const image = await new Promise<string>((resolve, reject) => {
      const child = spawn(pythonPath, [scriptPath], {
        cwd: agentsDir,
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: 30000,
      });

      let stdout = '';
      let stderr = '';
      child.stdout.on('data', (data: string) => { stdout += data; });
      child.stderr.on('data', (data: string) => { stderr += data; });

      child.on('close', (code: number) => {
        if (stderr) console.error('[PREVIEW API] Python stderr:', stderr);
        if (code !== 0) return reject(new Error(`Renderer exited with code ${code}`));
        const trimmed = stdout.trim();
        if (!trimmed) return reject(new Error('Empty response from renderer'));
        resolve(trimmed);
      });
      child.on('error', reject);

      child.stdin.end(JSON.stringify(sceneConfig));
    });

    return NextResponse.json({
      success: true,
      image,
      format: 'png',
    });
  } catch (error: any) {
    console.error('[PREVIEW API] Error:', error);
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 },
    );
  }
}
