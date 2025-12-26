#!/usr/bin/env bash
set -euo pipefail

# Helper to grow partition /dev/sda3 -> pvresize -> lvextend -> resize2fs
# Usage: sudo ./infra/resize_lv.sh

echo "*** Resize helper: will grow /dev/sda3, pvresize, lvextend and grow filesystem." 
echo "*** Make sure you have a backup/snapshot before proceeding."
read -p "Continue and apply changes? Type 'yes' to proceed: " ans
if [[ "$ans" != "yes" ]]; then
  echo "Aborted by user."
  exit 1
fi

echo "1) Show current layout"
lsblk
echo
sudo pvs || true
sudo vgs || true
sudo lvs || true
echo
FS_TYPE=$(findmnt -n -o FSTYPE /)
ROOT_DEV=$(findmnt -n -o SOURCE /)
echo "Root filesystem: $ROOT_DEV (type: $FS_TYPE)"

echo
echo "2) Install cloud-guest-utils (growpart) if missing"
apt-get update
apt-get install -y cloud-guest-utils || true

if ! command -v growpart >/dev/null 2>&1; then
  echo "growpart not available. Install cloud-guest-utils and retry.";
  exit 1
fi

echo
echo "3) Grow partition /dev/sda3 to fill disk"
sudo growpart /dev/sda 3 || { echo 'growpart failed'; exit 1; }

echo
echo "Partition table after growpart:"
lsblk

echo
echo "4) Resize PV to use new partition size"
sudo pvresize /dev/sda3 || { echo 'pvresize failed'; exit 1; }

echo
sudo pvs
sudo vgs

echo
echo "5) Extend LV to use all free space in VG"
sudo lvextend -l +100%FREE /dev/mapper/ubuntu--vg-ubuntu--lv || { echo 'lvextend failed'; exit 1; }

echo
sudo lvs

echo
echo "6) Grow filesystem ($FS_TYPE)"
if [[ "$FS_TYPE" == "ext4" ]]; then
  sudo resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv || { echo 'resize2fs failed'; exit 1; }
elif [[ "$FS_TYPE" == "xfs" ]]; then
  sudo xfs_growfs / || { echo 'xfs_growfs failed'; exit 1; }
else
  echo "Unknown filesystem type: $FS_TYPE. Manual intervention required."; exit 1
fi

echo
echo "Final state:"
df -h /
sudo pvs
sudo vgs
sudo lvs

echo 'Done.'
