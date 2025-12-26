# Infra (Vagrant) for UM Drive project

This `infra/` folder provides a minimal Vagrant-based environment to satisfy the virtualization requirement.

Structure
- `Vagrantfile` - defines two VMs: `nfs-server` and `app-node`.
- `provision/common.sh` - base packages and utilities
- `provision/nfs.sh` - sets up NFS server and exports `/nfsraid/projeto`
- `provision/docker.sh` - installs Docker and docker-compose on the app node

Quick start

1. Prerequisites:
   - Host with Vagrant and VirtualBox (or another provider) installed.
   - Enough disk and memory (recommended 4GB+ free).

2. Launch the infra:
```bash
cd infra
vagrant up
```

3. SSH to app node:
```bash
vagrant ssh app-node
# inside the VM
ls /home/vagrant/projetocliente    # should show files.json
docker --version
docker-compose --version
```

4. Run the project on the app node (inside VM):
```bash
cd /home/vagrant/projeto
# optionally build images
docker-compose up -d --build
```

Notes and caveats
- The NFS export is created on `nfs-server` at `/nfsraid/projeto` and mounted on `app-node:/home/vagrant/projetocliente`.
- NFS export allows the Vagrant private network `192.168.56.0/24`.
- For Windows hosts or other providers some adjustments may be necessary (see README top-level).

Testing
- After `vagrant up`, from the host you can run `vagrant ssh app-node -c "ls /home/vagrant/projetocliente"` to confirm the mount.

