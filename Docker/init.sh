#!/bin/bash
service postgresql start
su postgres -c 'echo "docker" | psql -f /initdb.sql'
service nginx start
service supervisor start
# supervisorctl start reversi-bot # already started
# python3 reversi-bot.py
