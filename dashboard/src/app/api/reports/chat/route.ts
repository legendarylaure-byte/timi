import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';
import { rateLimitMiddleware } from '@/lib/rate-limit';

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

const SYSTEM_PROMPT = `You are Vyom, an AI content strategist for a tech education YouTube channel called "Timi". You analyze content performance data and provide actionable recommendations.

You have access to the channel's real-time analytics. Use the context provided below to answer questions.

When responding:
- Be concise and data-driven
- Use markdown formatting (bold, lists, etc.)
- Include specific numbers and percentages when available
- You can suggest action cards using the format: [ACTION:label|type|target]
  - type "link": navigates to a dashboard page (e.g., /dashboard/archive)
  - type "trigger": triggers an action (e.g., run_pipeline)
- If the user asks about something outside your knowledge, say so honestly
- Keep responses under 500 words unless the user asks for detail
- Always tie recommendations back to data

Current context:
{context}

Previous conversation:
{history}`;

async function gatherContext(db: any) {
  try {
    const [videosSnap, channelSnap, metricsSnap, pipelineSnap, revenueSnap] = await Promise.all([
      db.collection('videos').orderBy('created_at', 'desc').limit(10).get(),
      db.collection('system').doc('channel_stats').get(),
      db.collection('pipeline_metrics').orderBy('created_at', 'desc').limit(20).get(),
      db.collection('system').doc('pipeline').get(),
      db.collection('monetization').doc('revenue').get(),
    ]);

    const channelData = channelSnap.data() || {};
    const pipelineData = pipelineSnap.data() || {};
    const revenueData = revenueSnap.data() || {};

    let successCount = 0;
    let totalPipelineRuns = 0;
    for (const doc of metricsSnap.docs || []) {
      const d = doc.data();
      totalPipelineRuns++;
      if (d.success) successCount++;
    }
    const pipelineSuccessRate = totalPipelineRuns > 0 ? Math.round((successCount / totalPipelineRuns) * 100) : 0;

    const recentVideos = videosSnap.docs.slice(0, 5).map((d: any) => {
      const v = d.data();
      return `- "${v.title || 'Untitled'}" (${v.format || 'shorts'}, ${v.views || 0} views, ${v.status || 'unknown'})`;
    }).join('\n');

    return `Channel Stats:
- Subscribers: ${channelData.subscribers || '0'}
- Total Views: ${channelData.total_views || '0'}
- Watch Hours: ${Math.round(parseFloat(channelData.total_watch_hours || '0'))}
- Videos: ${channelData.video_count || '0'}

Pipeline:
- Status: ${pipelineData.running ? 'Running' : 'Idle'}
- Success Rate: ${pipelineSuccessRate}% (${totalPipelineRuns} runs)

Revenue (MTD):
- $${revenueData.currentMonth || '0'} this month
- $${revenueData.estimatedYearly || '0'} estimated yearly
- RPM: $${revenueData.rpm || '0'}

Recent Videos:
${recentVideos || 'No videos yet'}`;
  } catch {
    return 'Unable to load context data.';
  }
}

async function saveMessage(db: any, sessionId: string, role: string, content: string, actions?: any[]) {
  try {
    await db.collection('reports').doc('chat_sessions').collection(sessionId).add({
      role,
      content,
      actions: actions || [],
      timestamp: new Date(),
    });
  } catch (_e: any) { /* best effort */ }
}

async function getHistory(db: any, sessionId: string): Promise<string> {
  try {
    const snap = await db.collection('reports').doc('chat_sessions')
      .collection(sessionId).orderBy('timestamp', 'asc').limit(20).get();
    return snap.docs.map((d: any) => {
      const m = d.data();
      return `${m.role === 'user' ? 'User' : 'Vyom'}: ${m.content}`;
    }).join('\n');
  } catch {
    return '';
  }
}

function extractActions(text: string): { cleanText: string; actions: Array<{ label: string; type: string; target: string }> } {
  const actions: Array<{ label: string; type: string; target: string }> = [];
  const cleanText = text.replace(/\[ACTION:(.*?)\|(.*?)\|(.*?)\]/g, (_, label, type, target) => {
    actions.push({ label, type, target });
    return '';
  });
  return { cleanText: cleanText.trim(), actions };
}

async function callGemini(prompt: string, apiKey?: string): Promise<string> {
  if (!apiKey) {
    return generateFallbackResponse(prompt);
  }

  try {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            temperature: 0.7,
            maxOutputTokens: 1024,
            topP: 0.9,
          },
        }),
      },
    );

    if (!res.ok) {
      const errText = await res.text();
      console.error('[CHAT] Gemini API error:', res.status, errText);
      return generateFallbackResponse(prompt);
    }

    const data = await res.json();
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
    if (!text) return generateFallbackResponse(prompt);
    return text;
  } catch (err) {
    console.error('[CHAT] Gemini call failed:', err);
    return generateFallbackResponse(prompt);
  }
}

function generateFallbackResponse(prompt: string): string {
  const lower = prompt.toLowerCase();

  if (lower.includes('performance') || lower.includes('how are') || lower.includes('summary')) {
    return `Here's what I can see from the data:

**Channel Overview**
- Track your subscriber and view growth on the **Performance Trends** tab
- Compare category performance in **Quality & Insights → Breakdown**

**Key Actions**
1. Check your best-performing category and double down on it
2. Review any underperforming videos for patterns
3. Monitor pipeline health for recurring failures

[ACTION:View Performance Trends|link|/dashboard/reports]
[ACTION:Check Pipeline Health|link|/dashboard/reports?tab=pipeline]
[ACTION:Review Archive|link|/dashboard/archive]`;
  }

  if (lower.includes('pipeline') || lower.includes('health') || lower.includes('error')) {
    return `**Pipeline Health Summary**

Your pipeline metrics are available in the **Pipeline Health** tab. Look for:
- **Success rate** — should be above 80% for healthy operation
- **Step durations** — unusually long steps may indicate issues
- **Recent errors** — check which agents are failing most

[ACTION:View Pipeline Health|link|/dashboard/reports]`;
  }

  if (lower.includes('improve') || lower.includes('grow') || lower.includes('suggestion') || lower.includes('recommend')) {
    return `**Growth Recommendations**

Based on common patterns for tech education channels:

1. **Consistency** — Regular uploads build audience trust
2. **Category focus** — Double down on your best-performing category
3. **Hook optimization** — Strong hooks in first 3 seconds increase retention
4. **Title testing** — A/B test titles to find what resonates
5. **Cross-platform** — Publish to all platforms for maximum reach

[ACTION:Set a Growth Goal|link|/dashboard/reports]
[ACTION:Review Category Performance|link|/dashboard/reports?tab=quality]`;
  }

  if (lower.includes('goal') || lower.includes('target') || lower.includes('milestone')) {
    return `**Goal Tracking**

Set and track goals in the **Goals & Forecast** tab:
- Subscriber milestones
- Revenue targets
- Video publishing goals
- Watch hour goals

The what-if simulator can help you understand the impact of changing your upload frequency.

[ACTION:View Goals|link|/dashboard/reports]`;
  }

  if (lower.includes('hello') || lower.includes('hi') || lower.includes('hey') || lower.includes('help')) {
    return `Hello! I'm Vyom, your AI content strategist. I can help you with:

- 📊 **Performance analysis** — "How are my videos performing?"
- 🔍 **Insights** — "What can I improve?"
- 🏥 **Pipeline health** — "Any errors or bottlenecks?"
- 🎯 **Growth strategy** — "How do I reach 1000 subscribers?"
- 📋 **Data queries** — "Which category performs best?"

What would you like to explore?`;
  }

  return `I've analyzed your request against the available data.

**What I know:**
- Your channel stats and video performance are visible on the **Reports** dashboard
- Pipeline health metrics are tracked in real-time
- Content gaps and category performance can help guide your strategy

**Suggested actions:**
- Visit the **Executive Summary** for a quick overview
- Check **Quality & Insights** for correlation analysis
- Review **Content Gaps** to find untapped opportunities

[ACTION:View Executive Summary|link|/dashboard/reports]
[ACTION:Check Content Gaps|link|/dashboard/reports]
[ACTION:View Archive|link|/dashboard/archive]`;
}

export async function POST(request: Request) {
  const rateLimitResponse = rateLimitMiddleware(request, 15, 60000);
  if (rateLimitResponse) return rateLimitResponse;

  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const { message, sessionId: existingSessionId } = body;
    if (!message) {
      return NextResponse.json({ success: false, error: 'Message is required' }, { status: 400 });
    }

    const db = getAdminFirestore();
    const sessionId = existingSessionId || `session_${user.uid}_${Date.now()}`;
    const apiKey = process.env.GEMINI_API_KEY || '';

    const [context, history] = await Promise.all([
      gatherContext(db),
      getHistory(db, sessionId),
    ]);

    const prompt = SYSTEM_PROMPT
      .replace('{context}', context)
      .replace('{history}', history || 'No previous conversation.')
      + `\n\nUser: ${message}\n\nVyom:`;

    const rawResponse = await callGemini(prompt, apiKey);
    const { cleanText, actions } = extractActions(rawResponse);

    await Promise.all([
      saveMessage(db, sessionId, 'user', message),
      saveMessage(db, sessionId, 'assistant', cleanText, actions),
    ]);

    return NextResponse.json({
      success: true,
      sessionId,
      message: cleanText,
      actions: actions.length > 0 ? actions : undefined,
    });
  } catch (error: any) {
    console.error('[CHAT] Error:', error);
    return NextResponse.json(
      { success: false, error: error.message || 'Chat failed' },
      { status: 500 },
    );
  }
}
