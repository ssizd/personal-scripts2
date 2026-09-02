const WORKFLOW_DISPATCH_URL =
  "https://api.github.com/repos/ssizd/personal-scripts2/actions/workflows/notify.yml/dispatches";

async function dispatchDiscordNotifier(env) {
  const response = await fetch(WORKFLOW_DISPATCH_URL, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "discord-notifier-scheduler",
      "X-GitHub-Api-Version": "2022-11-28"
    },
    body: JSON.stringify({ ref: "main" })
  });

  if (response.status !== 204) {
    const details = await response.text();
    throw new Error(`GitHub workflow dispatch failed (${response.status}): ${details}`);
  }

  console.log(JSON.stringify({
    event: "workflow_dispatched",
    workflow: "notify.yml",
    scheduledAt: new Date().toISOString()
  }));
}

export default {
  async fetch() {
    return Response.json({
      ok: true,
      service: "discord-notifier-scheduler"
    });
  },

  async scheduled(_controller, env) {
    await dispatchDiscordNotifier(env);
  }
};
