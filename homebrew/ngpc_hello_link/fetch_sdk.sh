#!/usr/bin/env bash
# Copy the NGPC SDK files this demo builds against from a local clone of
# https://github.com/ameliandev/ngpc-project-template (which bundles Ivan
# Mackintosh's 2003 NGPC framework). They are not redistributed here.
#
#   git clone https://github.com/ameliandev/ngpc-project-template
#   ./fetch_sdk.sh ../path/to/ngpc-project-template
#
# The template also ships the cc900 toolchain as install/ngpcbins_x86_x64.zip.
set -euo pipefail

if [ $# -ne 1 ] || [ ! -f "$1/library.c" ]; then
	echo "usage: $0 <path to ngpc-project-template clone>" >&2
	exit 1
fi

src="$1"
dst="$(cd "$(dirname "$0")" && pwd)"

for f in library.c library.h library.inc ngpc.h ngpc.lcf system.lib carthdr.h colors.h; do
	cp "$src/$f" "$dst/$f"
done

# Cartridge title: exactly 12 characters, space-padded.
sed -i 's/const char CartTitle\[12\] = ".*";/const char CartTitle[12] = "NGPC LINK01 ";/' "$dst/carthdr.h"

echo "SDK files copied into $dst"
