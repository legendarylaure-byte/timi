import { NextResponse } from 'next/server';
import { execSync } from 'child_process';

interface ContainerInfo {
  name: string;
  image: string;
  status: string;
  state: string;
  uptime: string;
  ports: string;
  cpu: string;
  memory: string;
}

function isVercel(): boolean {
  return process.env.VERCEL === '1' || process.env.VERCEL_URL !== undefined;
}

export async function GET() {
  if (isVercel()) {
    return NextResponse.json({
      available: false,
      daemon: false,
      reason: 'vercel_serverless',
      containers: [],
      message: 'Docker not available in cloud (Vercel serverless)',
    });
  }

  try {
    const raw = execSync(
      `docker ps -a --format '{{json .}}' --filter "name=timi"`,
      { timeout: 5000, encoding: 'utf-8' }
    ).toString().trim();

    if (!raw) {
      return NextResponse.json({
        available: false,
        containers: [],
        message: 'No timi containers found',
      });
    }

    const lines = raw.split('\n').filter(Boolean);
    const containers: ContainerInfo[] = lines.map((line: string) => {
      try {
        const c = JSON.parse(line);
        return {
          name: c.Names,
          image: c.Image,
          status: c.Status,
          state: c.State,
          uptime: c.Status,
          ports: c.Ports || '',
          cpu: '',
          memory: '',
        };
      } catch {
        return null;
      }
    }).filter(Boolean) as ContainerInfo[];

    const statsRaw = execSync(
      `docker stats --no-stream --format '{{json .}}' $(docker ps -q --filter "name=timi")`,
      { timeout: 5000, encoding: 'utf-8' }
    ).toString().trim();

    if (statsRaw) {
      const statsLines = statsRaw.split('\n').filter(Boolean);
      statsLines.forEach((line: string) => {
        try {
          const s = JSON.parse(line);
          const idx = containers.findIndex(c => c.name.startsWith(s.Name) || s.Name.startsWith(c.name));
          if (idx >= 0) {
            containers[idx].cpu = s.CPUPerc || '';
            containers[idx].memory = s.MemPerc || '';
          }
        } catch {}
      });
    }

    const allRunning = containers.every(c => c.state === 'running');
    const pipelineContainer = containers.find(
      c => c.name.toLowerCase().includes('pipeline')
    );

    return NextResponse.json({
      available: true,
      daemon: true,
      all_running: allRunning,
      container_count: containers.length,
      pipeline: pipelineContainer || null,
      containers,
    });
  } catch (error: any) {
    if (isVercel() || error.code === 'ENOENT' || error.stderr?.includes('Cannot connect')) {
      return NextResponse.json({
        available: false,
        daemon: false,
        reason: isVercel() ? 'vercel_serverless' : undefined,
        containers: [],
        error: error.code === 'ENOENT' ? 'Docker daemon not reachable' : error.message,
      });
    }
    return NextResponse.json({
      available: false,
      containers: [],
      error: error.message,
    });
  }
}
