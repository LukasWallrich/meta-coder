#!/usr/bin/env bash
# Uninstall a release installed by install.sh. User data and Pixi are kept.
# Usage: bash scripts/uninstall.sh
set -euo pipefail

if [ "$#" -ne 0 ]; then
  echo "Usage: bash scripts/uninstall.sh (preserves user data and Pixi)" >&2
  exit 1
fi

: "${HOME:?HOME must be set}"
if [ "$(uname -s)" = "Darwin" ]; then
  data_root="$HOME/Library/Application Support/Meta-Coder"
else
  data_root="${XDG_DATA_HOME:-$HOME/.local/share}/meta-coder"
fi
app_root="$data_root/app"
launcher="$HOME/.local/bin/meta-coder"

# Leave a launcher from another installation (e.g. pip) alone.
if [ -f "$launcher" ] && grep -Fq "exec pixi run --manifest-path \"$app_root/" "$launcher"; then
  rm -f -- "$launcher"
elif [ -e "$launcher" ] || [ -L "$launcher" ]; then
  echo "Keeping launcher not recognized as this release installation: $launcher"
fi
rm -rf -- "$app_root"

echo "MetaCoder release installation removed."
echo "Projects, settings, saved API keys, and Pixi have been preserved."
echo "User data location: $data_root (or your META_CODER_HOME override)."
