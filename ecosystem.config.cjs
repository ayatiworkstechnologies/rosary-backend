/**
 * Production PM2 process definitions.
 *
 * The API intentionally binds to loopback. nginx is the only public TLS
 * entrypoint; port 8016 must also be blocked by the host firewall.
 */
module.exports = {
  apps: [
    {
      name: "rosary-api",
      cwd: "/var/www/rosary-backend",
      script: "venv/bin/python",
      args: "-m uvicorn app.main:app --host 127.0.0.1 --port 8016",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      kill_timeout: 10000,
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
    {
      name: "rosary-email-worker",
      cwd: "/var/www/rosary-backend",
      script: "venv/bin/python",
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
