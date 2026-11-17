#!/usr/bin/env bash
# Future-device provisioning. Default is a plan; never run apt on this workstation.
set -euo pipefail
packages=(tmux git curl wget python3 python3-venv minicom picocom openssh-client openssh-server man-db manpages less nano htop usbutils)
if [[ ${1:---plan} != --apply ]]; then
  printf 'Fielddeck 7: Raspberry Pi OS 64-bit Desktop (Trixie)\nPackages: %s\n' "${packages[*]}"
  printf 'On the Pi, use --apply to install. Configure SSH keys and landscape orientation through Imager / Control Centre.\n'
  exit 0
fi
if [[ ! -r /proc/device-tree/model ]] || ! tr -d '\0' </proc/device-tree/model | grep -q 'Raspberry Pi 4 Model B'; then
  printf 'Provisioning requires the selected Raspberry Pi 4 Model B.\n' >&2
  exit 2
fi
if [[ $EUID -eq 0 ]]; then
  printf 'Run as the intended desktop user, with sudo available.\n' >&2
  exit 2
fi
sudo apt-get update
sudo apt-get install -y "${packages[@]}"
mkdir -p "$HOME/Fielddeck/docs"
package_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cp -- "$package_dir/README.md" "$package_dir/ASSEMBLY.md" "$package_dir/CONNECTIONS.md" "$HOME/Fielddeck/docs/"
printf 'Offline local reference files copied to ~/Fielddeck/docs.\n'
printf 'Set SSH public-key authentication in Imager/Control Centre, select landscape orientation, then run healthcheck.sh on the Pi.\n'
