const REPOSITORY_WORKFLOWS_URL =
  "https://api.github.com/repos/ssizd/personal-scripts2/actions/workflows";

const PATREON_CRON = "12 * * * *";

async function dispatchWorkflow(workflow, env) {
  const response = await fetch(`${REPOSITORY_WORKFLOWS_URL}/${workflow}/dispatches`, {
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
    throw new Error(`GitHub workflow dispatch failed for ${workflow} (${response.status})`);
  }

  console.log(JSON.stringify({
    event: "workflow_dispatched",
    workflow,
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

  async scheduled(controller, env) {
    const workflow = controller.cron === PATREON_CRON
      ? "patreon_notify.yml"
      : "notify.yml";

    await dispatchWorkflow(workflow, env);
  }
};
