#!/usr/bin/env bash
set -euo pipefail

# Provision NFS server: create export and start server
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends nfs-kernel-server

# Create export directory
mkdir -p /nfsraid/projeto
chown -R nobody:nogroup /nfsraid/projeto
chmod 0777 /nfsraid/projeto

# Add example seed file so folder is not empty
if [ ! -f /nfsraid/projeto/files.json ]; then
  echo '[]' > /nfsraid/projeto/files.json
fi

# Add export (allow the Vagrant private network)
if ! grep -q "^/nfsraid/projeto" /etc/exports 2>/dev/null; then
  echo "/nfsraid/projeto 192.168.56.0/24(rw,sync,no_subtree_check,no_root_squash)" >> /etc/exports
fi

# Apply export
exportfs -ra
systemctl enable --now nfs-kernel-server || true

