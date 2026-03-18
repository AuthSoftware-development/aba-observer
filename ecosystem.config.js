const path = require("path");

module.exports = {
  apps: [
    {
      name: "the-i-backend",
      script: "server.py",
      interpreter: "python",
      cwd: __dirname,
      env: {
        GOOGLE_API_KEY: process.env.GOOGLE_API_KEY || "",
      },
      watch: false,
      autorestart: true,
      max_restarts: 5,
    },
    {
      name: "the-i-frontend",
      script: path.join(__dirname, "frontend", "node_modules", "next", "dist", "bin", "next"),
      args: "start -p 3018",
      cwd: path.join(__dirname, "frontend"),
      interpreter: "node",
      watch: false,
      autorestart: true,
      max_restarts: 5,
    },
  ],
};
