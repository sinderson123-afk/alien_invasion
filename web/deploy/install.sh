#!/bin/sh
set -eu
# Run as root after copying web/ into /opt/alien-invasion/web.
id alien-invasion >/dev/null 2>&1 || useradd --system --home /var/lib/alien-invasion --shell /usr/sbin/nologin alien-invasion
install -d -m 700 -o alien-invasion -g alien-invasion /var/lib/alien-invasion
python3 -m venv /opt/alien-invasion/venv
/opt/alien-invasion/venv/bin/pip install -r /opt/alien-invasion/web/requirements.txt
if [ ! -e /etc/alien-invasion.env ]; then
    install -m 600 /opt/alien-invasion/web/deploy/env.example /etc/alien-invasion.env
fi
install -m 644 /opt/alien-invasion/web/deploy/alien-invasion*.service /etc/systemd/system/
install -m 644 /opt/alien-invasion/web/deploy/alien-invasion-backup.timer /etc/systemd/system/
if [ ! -e /etc/nginx/sites-available/alien-invasion ]; then
    install -m 644 /opt/alien-invasion/web/deploy/nginx.conf /etc/nginx/sites-available/alien-invasion
fi
ln -sfn /etc/nginx/sites-available/alien-invasion /etc/nginx/sites-enabled/alien-invasion
nginx -t
systemctl daemon-reload
systemctl enable --now redis-server alien-invasion alien-invasion-backup.timer
systemctl restart alien-invasion
systemctl reload nginx
