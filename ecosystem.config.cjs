/**
 * Devteam-managed email worker only.
 *
 * The production FastAPI process is independently root-managed under the PM2
 * name `rosary-backend`. Do not add it to this file or use this file to reload
 * it. Point the worker at the exact approved versioned backend release.
 */
const releaseDir = process.env.ROSARY_BACKEND_RELEASE_DIR;

if (!releaseDir) {
  throw new Error("ROSARY_BACKEND_RELEASE_DIR must name the approved release");
}

module.exports = {
  apps: [
    {
      name: "rosary-email-worker",
      cwd: releaseDir,
      script: `${releaseDir}/venv/bin/python`,
      args: "-m app.workers.email_delivery_worker",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
