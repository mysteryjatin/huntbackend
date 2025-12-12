module.exports = {
  apps: [{
    name: 'huntbackend',
    script: 'venv/bin/python',
    args: '-m uvicorn main:app --host 0.0.0.0 --port 8000',
    cwd: '/var/backend/huntbackend',
    interpreter: 'none',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production',
      PYTHONUNBUFFERED: '1'
    },
    error_file: './logs/pm2-error.log',
    out_file: './logs/pm2-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true
  }]
};


