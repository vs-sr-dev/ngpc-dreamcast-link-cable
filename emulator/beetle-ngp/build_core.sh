#!/usr/bin/env bash
# Fetch beetle-ngp-libretro at the commit the patch was made against, apply
# the link-cable patch, build the Windows core and copy it to build/.
#
# Run from an MSYS2 shell with the mingw64 toolchain installed
# (pacman -S mingw-w64-x86_64-gcc make git):
#
#   ./emulator/beetle-ngp/build_core.sh
#
# Env overrides:
#   UPSTREAM   git URL or local path of beetle-ngp-libretro
#   WORKDIR    where the clone goes (default: build/beetle-ngp-libretro)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
UPSTREAM="${UPSTREAM:-https://github.com/libretro/beetle-ngp-libretro.git}"
COMMIT=0c81ce8
WORKDIR="${WORKDIR:-$ROOT/build/beetle-ngp-libretro}"
PATCH="$HERE/0001-ngpc-link-cable-backend.patch"

mkdir -p "$ROOT/build"
if [ ! -d "$WORKDIR/.git" ]; then
	git -c core.autocrlf=false clone "$UPSTREAM" "$WORKDIR"
fi
cd "$WORKDIR"
git checkout -q "$COMMIT"
if git apply --check "$PATCH" 2>/dev/null; then
	git apply "$PATCH"
elif git apply --check -R "$PATCH" 2>/dev/null; then
	echo "patch already applied"
else
	echo "patch does not apply cleanly to $COMMIT" >&2
	exit 1
fi

# TRAP: MSYS2 bash strips TMPDIR on startup, and gcc then fails with
# "Cannot create temporary file in C:\WINDOWS\". Re-inject it through an
# env.exe SHELL wrapper so every recipe sees it.
mkdir -p .tmp
tmp="$(cygpath -m "$PWD/.tmp")"
export PATH="/mingw64/bin:$PATH"
make platform=win -j"$(nproc)" \
	SHELL="/usr/bin/env TMPDIR=$tmp TEMP=$tmp TMP=$tmp /usr/bin/bash"

cp mednafen_ngp_libretro.dll "$ROOT/build/"
echo "OK: $ROOT/build/mednafen_ngp_libretro.dll"
