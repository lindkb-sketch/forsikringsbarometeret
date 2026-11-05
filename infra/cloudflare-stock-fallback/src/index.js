// Reserve scheduler. GitHub remains the primary scheduler and publisher.
// Cloudflare only dispatches when GitHub has not started a recent run.
const OWNER = 'lindkb-sketch';
const REPO = 'forsikringsbarometeret';
const WORKFLOW = 'stock-prices.yml';
const API = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}`;
const RECENT_MS = 20 * 60 * 1000;

function marketOpenWindow(date) {
  return [
    ['Europe/Oslo', 8 * 60 + 45, 16 * 60 + 45],
    ['Europe/Copenhagen', 8 * 60 + 45, 17 * 60 + 20],
    ['Europe/Helsinki', 9 * 60 + 45, 18 * 60 + 45],
  ].some(([timeZone, start, end]) => {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat('en-GB', {
        timeZone, weekday: 'short', hour: '2-digit', minute: '2-digit',
        hourCycle: 'h23',
      }).formatToParts(date).map(p => [p.type, p.value])
    );
    if (['Sat', 'Sun'].includes(parts.weekday)) return false;
    const minute = Number(parts.hour) * 60 + Number(parts.minute);
    return minute >= start && minute <= end;
  });
}

async function github(path, token, init = {}) {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'forsikringsbarometeret-stock-fallback',
      ...(init.headers || {}),
    },
  });
  if (!response.ok) throw new Error(`GitHub API HTTP ${response.status}`);
  return response;
}

export default {
  async scheduled(event, env) {
    if (!marketOpenWindow(new Date(event.scheduledTime))) return;
    if (!env.GITHUB_TOKEN) throw new Error('GITHUB_TOKEN secret is required');
    // Fail closed: if the run history cannot be read, do not trigger duplicates.
    const response = await github(`${API}/runs?per_page=15`, env.GITHUB_TOKEN);
    const { workflow_runs: runs = [] } = await response.json();
    const now = event.scheduledTime;
    const recent = runs.some(run => {
      const created = Date.parse(run.created_at);
      if (!Number.isFinite(created) || created > now + 60_000 ||
          now - created > RECENT_MS) return false;
      // A failed recent run may be retried by the backup; a successful,
      // queued or running run must not be duplicated.
      return run.status !== 'completed' || run.conclusion === 'success';
    });
    if (recent) return;
    await github(`${API}/dispatches`, env.GITHUB_TOKEN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'main' }),
    });
    console.log('Dispatched stock fallback workflow');
  },
};
