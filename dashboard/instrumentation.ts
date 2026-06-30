export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { getAdminFirestore } = await import('@/lib/firebase-admin');

    const ping = async () => {
      try {
        const db = getAdminFirestore();
        await db.collection('system').doc('heartbeat').set({
          last_heartbeat: new Date().toISOString(),
          source: 'dashboard-server',
          pid: process.pid,
          uptime_minutes: Math.round(process.uptime() / 60),
          node_version: process.version,
        }, { merge: true });
      } catch {
        // best-effort
      }
    };

    await ping();
    setInterval(ping, 300_000); // every 5 minutes
  }
}
