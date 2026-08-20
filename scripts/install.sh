#!/usr/bin/env bash
# MetaCoder installer (macOS/Linux) — todo.md step 20 / plan.md "A1. Shape,
# install, and local-only security". Downloads a versioned release bundle
# (source + pixi.lock, built by build_release.sh), installs its locked
# environment via Pixi, and drops a `meta-coder` launcher on PATH. Re-running
# this script installs the newest version and repoints the launcher — nothing
# needs to be manually removed first.
#
# Usage:
#   curl -fsSL <release-base-url>/install.sh | sh
# Configuration (env vars):
#   META_CODER_RELEASE_BASE_URL  Where release bundles + latest.txt live.
#                                 REQUIRED — see the error below for why this
#                                 has no built-in default yet.
#   META_CODER_VERSION           Install this exact version instead of latest.
set -euo pipefail

app_name="MetaCoder"
app_slug="meta-coder"
data_dir_name="Meta-Coder"

# --- 1. Where do bundles come from? ------------------------------------
# There is no hosted release feed yet (no GitHub repo/releases configured for
# this project). Point this at wherever `dist/meta-coder-<version>.tar.gz`
# (from build_release.sh) and a `latest.txt` containing the newest version
# number get published — e.g. a GitHub Releases download URL once one exists.
base_url="${META_CODER_RELEASE_BASE_URL:-}"
if [ -z "$base_url" ]; then
  echo "error: META_CODER_RELEASE_BASE_URL is not set." >&2
  echo "       This installer has no release feed configured yet — set it to" >&2
  echo "       wherever release bundles are published (see scripts/build_release.sh)" >&2
  echo "       and re-run, e.g.:" >&2
  echo "         META_CODER_RELEASE_BASE_URL=https://github.com/<org>/<repo>/releases/latest/download sh install.sh" >&2
  exit 1
fi
base_url="${base_url%/}"

# --- 2. Which version? ---------------------------------------------------
version="${META_CODER_VERSION:-}"
if [ -z "$version" ]; then
  version="$(curl -fsSL "$base_url/latest.txt")" || {
    echo "error: could not fetch $base_url/latest.txt to determine the latest version." >&2
    exit 1
  }
fi
version="$(printf '%s' "$version" | tr -d '[:space:]')"
if [ -z "$version" ]; then
  echo "error: resolved an empty version string." >&2
  exit 1
fi
echo "Installing $app_name $version..."

# --- 3. Where does it go? (mirrors meta_coder/paths.py's app_data_dir) --
if [ "$(uname -s)" = "Darwin" ]; then
  data_root="$HOME/Library/Application Support/$data_dir_name"
else
  data_root="${XDG_DATA_HOME:-$HOME/.local/share}/$app_slug"
fi
app_root="$data_root/app"
install_dir="$app_root/$version"
bin_dir="$HOME/.local/bin"
launcher="$bin_dir/meta-coder"

# --- 4. Download + extract -----------------------------------------------
mkdir -p "$install_dir" "$bin_dir"
tmp_tarball="$(mktemp)"
trap 'rm -f "$tmp_tarball"' EXIT
curl -fsSL "$base_url/meta-coder-$version.tar.gz" -o "$tmp_tarball" || {
  echo "error: could not download $base_url/meta-coder-$version.tar.gz" >&2
  exit 1
}
tar -xzf "$tmp_tarball" -C "$install_dir" --strip-components=1

# --- 5. Bootstrap Pixi if this machine doesn't have it yet ---------------
if ! command -v pixi >/dev/null 2>&1; then
  echo "Pixi not found — installing it (see https://pixi.sh)..."
  curl -fsSL https://pixi.sh/install.sh | sh
  # The official installer places pixi here; add it to this script's PATH so
  # the `pixi install` call below can find it without a new shell.
  export PATH="$HOME/.pixi/bin:$PATH"
fi
if ! command -v pixi >/dev/null 2>&1; then
  echo "error: pixi installation did not put 'pixi' on PATH. Open a new shell and re-run." >&2
  exit 1
fi

# --- 6. Materialize the locked environment --------------------------------
# --locked (not --frozen) so a bundle whose pixi.lock doesn't actually match
# its own manifest fails loudly here rather than silently resolving fresh.
pixi install --manifest-path "$install_dir/pyproject.toml" --locked

# --- 7. Launcher shim ------------------------------------------------------
cat > "$launcher" <<EOF
#!/usr/bin/env bash
exec pixi run --manifest-path "$install_dir/pyproject.toml" start "\$@"
EOF
chmod +x "$launcher"

# --- 8. Drop stale versions — "re-running the installer updates in place" -
for existing in "$app_root"/*/; do
  existing="${existing%/}"
  if [ "$(basename "$existing")" != "$version" ]; then
    rm -rf "$existing"
  fi
done

echo ""
echo "$app_name $version installed."
if ! command -v meta-coder >/dev/null 2>&1; then
  echo "Add $bin_dir to your PATH (e.g. in ~/.zshrc or ~/.bashrc), then open a new shell."
fi
echo "Run it with: meta-coder"
