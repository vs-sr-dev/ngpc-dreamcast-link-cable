#!/usr/bin/env bash
# Build bin/main.ngp with the Toshiba cc900 toolchain (ngpcbins). MSYS2 bash.
#
#   export THOME=/c/ngpcbins/T900     # where you unzipped ngpcbins
#   ./fetch_sdk.sh /path/to/ngpc-project-template   # once
#   ./build.sh
#
# TRAP: THOME and PATH entries must use the MSYS2 /c/ mount style, NOT C:/ --
# `which` resolution silently fails with C:/ paths even if `ls` on the same
# path succeeds, and cc900 finds its thc1/thc2 passes through PATH.
set -euo pipefail

cd "$(dirname "$0")"

if [ -z "${THOME:-}" ]; then
	echo "THOME is not set (expected <ngpcbins>/T900, MSYS2 style, e.g. /c/ngpcbins/T900)" >&2
	exit 1
fi
if [ ! -f library.c ]; then
	echo "SDK files missing: run ./fetch_sdk.sh <path to ngpc-project-template> first" >&2
	exit 1
fi

export PATH="$THOME/BIN:$PATH"

# Use the vintage GNU Make 3.78 bundled in ngpcbins (avoids host `make` dep).
exec "$THOME/BIN/MAKE.EXE" "$@"
