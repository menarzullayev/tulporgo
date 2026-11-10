#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu 24.04 LTS VPS (run as root). Idempotent.
#   curl -fsSL https://raw.githubusercontent.com/menarzullayev/tulporgo/main/deploy/scripts/bootstrap-vps.sh -o bootstrap.sh
#   less bootstrap.sh && bash bootstrap.sh
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }

user=tulporgo
dir=/opt/tulporgo

echo "== packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -yq
apt-get install -yq ca-certificates curl git ufw fail2ban unattended-upgrades

echo "== Docker (official apt repository)"
if ! command -v docker >/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

echo "== firewall: ssh, http, https only"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

echo "== automatic security updates, fail2ban"
dpkg-reconfigure -f noninteractive unattended-upgrades
systemctl enable --now fail2ban

echo "== deploy user and checkout"
id "$user" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$user"
usermod -aG docker "$user"
if [[ ! -d "$dir/.git" ]]; then
    git clone https://github.com/menarzullayev/tulporgo.git "$dir"
fi
chown -R "$user:$user" "$dir"

cat <<EOF

Done. Next steps (as $user):
  sudo -iu $user
  cd $dir/deploy && cp .env.example .env && chmod 600 .env && nano .env
  ./scripts/deploy.sh

Recommended by hand (not automated, to avoid locking you out):
  - SSH keys only: set "PasswordAuthentication no" in /etc/ssh/sshd_config.d/ after your key works.
EOF
