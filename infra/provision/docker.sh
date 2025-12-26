#!/usr/bin/env bash
set -euo pipefail

# Install Docker and docker-compose (standalone) on app node
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends apt-transport-https ca-certificates curl gnupg lsb-release

# Install Docker (from distro packages)
apt-get install -y --no-install-recommends docker.io
systemctl enable --now docker || true

# Add vagrant to docker group
if id -u vagrant >/dev/null 2>&1; then
  usermod -aG docker vagrant || true
fi

# Install docker-compose (standalone binary v1.29.2) - fallback to v2 plugin if not available
DOCKER_COMPOSE_BIN=/usr/local/bin/docker-compose
if [ ! -x "$DOCKER_COMPOSE_BIN" ]; then
  curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o "$DOCKER_COMPOSE_BIN"
  chmod +x "$DOCKER_COMPOSE_BIN"
fi

# Create project directory and ensure permissions
mkdir -p /home/vagrant/projeto
chown -R vagrant:vagrant /home/vagrant/projeto

