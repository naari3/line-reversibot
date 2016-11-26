import multiprocessing

# Server Socket
bind = 'unix:/tmp/reversi-bot.sock'
backlog = 2048

# Worker Processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
max_requests = 0
timeout = 30
keepalive = 2
debug = False
spew = False

# Logging
logfile = '/var/log/reversi/bot.log'
loglevel = 'info'
logconfig = None

# Process Name
proc_name = 'reversi-bot'
