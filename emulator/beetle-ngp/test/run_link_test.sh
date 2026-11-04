#!/usr/bin/env bash
# Link the harness against the objects build_core.sh produced, and run the
# test: no RetroArch, no ROM. MSYS2 MINGW64 shell, after build_core.sh.
#
#   ./emulator/beetle-ngp/test/run_link_test.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
CORE="${WORKDIR:-$ROOT/build/beetle-ngp-libretro}"
OUT="$ROOT/build/link_harness.exe"

if [ ! -f "$CORE/mednafen/ngp/system.o" ]; then
	echo "core objects not found in $CORE: run emulator/beetle-ngp/build_core.sh first" >&2
	exit 1
fi

mkdir -p "$CORE/.tmp"
export TMPDIR="$(cygpath -m "$CORE/.tmp")" TMP="$(cygpath -m "$CORE/.tmp")" TEMP="$(cygpath -m "$CORE/.tmp")"
export PATH="/mingw64/bin:$PATH"

gcc -c -O1 "$HERE/link_harness.c" -o "$ROOT/build/link_harness.o"
g++ -o "$OUT" "$ROOT/build/link_harness.o" $(find "$CORE" -name '*.o' -not -path '*/.tmp/*') \
	-static-libgcc -static-libstdc++ -lwinmm -lws2_32 -lm

python "$HERE/link_test.py" "$OUT"
