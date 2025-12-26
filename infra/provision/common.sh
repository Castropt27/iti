#!/usr/bin/env bash
set -euo pipefail

# Common provisioning steps for both nfs-server and app-node
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates apt-transport-https gnupg2 curl sudo

# Ensure vagrant user exists and has sudo
if ! id -u vagrant >/dev/null 2>&1; then
  useradd -m -s /bin/bash vagrant
  echo "vagrant ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/vagrant
fi

# Install some useful packages
apt-get install -y --no-install-recommends net-tools iproute2 nfs-common dnsutils

# Disable swap (optional for some k8s tests)
swapoff -a || true

# Sysctl tuning for NFS (if needed)
cat <<'EOF' > /etc/sysctl.d/99-nfs.conf
net.ipv4.ip_forward=1
EOF
sysctl --system || true

