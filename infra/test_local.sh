#!/usr/bin/env bash
set -euo pipefail

# Local helper to start the infra and do basic checks
cd "$(dirname "$0")"

echo "Bringing Vagrant VMs up..."
vagrant up

echo "Checking NFS mount on app-node"
vagrant ssh app-node -c "mount | grep projetocliente || true"

echo "Listing mounted path"
vagrant ssh app-node -c "ls -la /home/vagrant/projetocliente || true"

echo "Docker available on app-node"
vagrant ssh app-node -c "docker --version || true; /usr/local/bin/docker-compose --version || true"

echo "Done. If everything looks OK, you can 'vagrant ssh app-node' and run the project's docker-compose there."
