#!/usr/bin/env bash
# Install Docker Engine + Compose inside WSL2 (Ubuntu/Debian).
# Recommended WSL setup: use this OR Docker Desktop with WSL integration — not both.
#
# Usage (in WSL):
#   chmod +x scripts/install-docker-wsl.sh
#   ./scripts/install-docker-wsl.sh
#   # log out and back in (or: newgrp docker)
#   docker run hello-world
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "Detected WSL."
else
  echo "Warning: this does not look like WSL — script is intended for WSL2 Ubuntu/Debian."
fi

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run as your normal user (script uses sudo internally)." >&2
  exit 1
fi

echo "=== Removing conflicting packages (if any) ==="
sudo apt-get remove -y docker docker-engine docker.io containerd runc docker-compose-v2 2>/dev/null || true

echo "=== Installing prerequisites ==="
sudo apt-get update -qq
sudo apt-get install -y ca-certificates curl gnupg

echo "=== Adding Docker official apt repository ==="
sudo install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
fi

ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

echo "=== Installing Docker Engine + Compose plugin ==="
sudo apt-get update -qq
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "=== Enabling systemd in WSL (required for service start) ==="
if grep -qi microsoft /proc/version 2>/dev/null; then
  sudo tee /etc/wsl.conf >/dev/null <<'EOF'
[boot]
systemd=true
EOF
  echo "Wrote /etc/wsl.conf with systemd=true"
  echo "IMPORTANT: From Windows PowerShell run:  wsl --shutdown"
  echo "Then reopen WSL before continuing."
fi

echo "=== Adding ${USER} to docker group ==="
sudo usermod -aG docker "${USER}"

echo "=== Starting Docker ==="
if command -v systemctl >/dev/null && systemctl is-system-running >/dev/null 2>&1; then
  sudo systemctl enable --now docker
else
  echo "systemd not running yet — after wsl --shutdown, run:  sudo systemctl start docker"
fi

cat <<'EOF'

=== Installation complete ===

Next steps:
  1. If WSL: run `wsl --shutdown` in Windows PowerShell, then reopen your distro
  2. Activate group:  newgrp docker   (or log out/in)
  3. Test:            docker run hello-world
  4. Start proxy:     ./scripts/start.sh

Tips:
  - Keep the repo on the Linux filesystem (~/...) not /mnt/c/...
  - Prefer Docker Desktop OR in-WSL docker-ce — avoid running both
  - If build fails on /mnt/c, move project to ~/

EOF
