#!/usr/bin/env bash
# Builds a versioned release bundle (todo.md step 20 / plan.md Architecture):
# a source archive of one git ref, including pixi.lock, that install.sh/
# install.ps1 later download and unpack. Bootstrapping the environment
# (`pixi install`) happens on the end user's machine at install time, not
# here — this script only has to produce the archive.
#
# Usage: scripts/build_release.sh [ref]
#   ref defaults to HEAD. The version number is read from pyproject.toml's
#   [project].version, not derived from the ref name, so it stays correct
#   even when building from a branch rather than a tag.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

ref="${1:-HEAD}"

version="$(git show "$ref:pyproject.toml" | sed -n 's/^version = "\(.*\)"$/\1/p' | head -n1)"
if [ -z "$version" ]; then
  echo "error: could not read [project].version from pyproject.toml at $ref" >&2
  exit 1
fi

if ! git cat-file -e "$ref:pixi.lock" 2>/dev/null; then
  echo "error: $ref has no pixi.lock — run 'pixi install' and commit it before releasing." >&2
  exit 1
fi

mkdir -p dist
bundle_name="meta-coder-${version}"
out_path="dist/${bundle_name}.tar.gz"

git archive --format=tar.gz --prefix="${bundle_name}/" -o "$out_path" "$ref"

echo "Built $out_path (version $version, from $ref)"
