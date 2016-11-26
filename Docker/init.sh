#!/bin/bash
service postgresql start
su postgres -c 'echo "docker" | psql -f /initdb.sql'
python3 reversi-bot.py
