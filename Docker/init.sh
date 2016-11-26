#!/bin/bash
service postgresql start
su postgres -c 'echo "docker" | psql -f /initdb.sql'
service nginx start
# service supervisor start
# supervisorctl start reversi-bot # already started
# python3 reversi-bot.py
cd /app
DATABASE_URL="postgres://docker:docker@127.0.0.1:5432/reversi_db" /usr/local/bin/gunicorn reversi-bot:app --config /app/gunicorn-config.py
