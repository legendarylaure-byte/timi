import { NextResponse } from 'next/server';

const COST_DIR = process.env.AGENTS_DIR || '';
const COST_LOG = COST_DIR ? `${COST_DIR}/data/costs/cost_log.csv` : '';

export async function GET() {
  try {
    if (!COST_LOG) {
      return NextResponse.json({
        total_cost: 0,
        by_caller: {},
        by_day: {},
        llm_calls: 0,
        stock_calls: 0,
        note: 'AGENTS_DIR not configured — cost tracking requires agents directory path',
      });
    }

    const fs = await import('fs');
    if (!fs.existsSync(COST_LOG)) {
      return NextResponse.json({ total_cost: 0, by_caller: {}, by_day: {}, llm_calls: 0, stock_calls: 0 });
    }

    const content = fs.readFileSync(COST_LOG, 'utf-8').trim();
    if (!content) {
      return NextResponse.json({ total_cost: 0, by_caller: {}, by_day: {}, llm_calls: 0, stock_calls: 0 });
    }

    const lines = content.split('\n');
    const headers = lines[0].split(',');
    const total: Record<string, number> = {};
    const byCaller: Record<string, number> = {};
    const byDay: Record<string, number> = {};
    let llmCalls = 0;
    let stockCalls = 0;

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(',');
      if (cols.length < 5) continue;
      const caller = cols[1]?.trim() || 'unknown';
      const cost = parseFloat(cols[4]?.trim() || '0');
      const day = (cols[0]?.trim() || '').slice(0, 10);

      total.cost = (total.cost || 0) + cost;
      byCaller[caller] = (byCaller[caller] || 0) + cost;
      byDay[day] = (byDay[day] || 0) + cost;
      if (caller.startsWith('stock:')) stockCalls++;
      else llmCalls++;
    }

    return NextResponse.json({
      total_cost: Math.round((total.cost || 0) * 10000) / 10000,
      by_caller: byCaller,
      by_day: byDay,
      llm_calls: llmCalls,
      stock_calls: stockCalls,
    });
  } catch {
    return NextResponse.json({ total_cost: 0, by_caller: {}, by_day: {}, llm_calls: 0, stock_calls: 0 });
  }
}
