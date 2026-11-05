#!/bin/bash
# Build dc_link_probe.elf (Flycast) and dc_link_probe.bin (serial loader) with KallistiOS (pure KOS, no extra libraries).
#
# Either:
#   - a native KOS install:   source /opt/toolchains/dc/kos/environ.sh && ./build.sh
#   - a Docker image with KOS at /opt/toolchains/dc/kos:
#         KOS_DOCKER_IMAGE=<your image> ./build.sh
#
# We built ours in a Fedora + KallistiOS image made from the Simulant
# project's Dreamcast Dockerfile (gitlab.com/simulant/simulant,
# platforms/dreamcast/Dockerfile). Any working KOS toolchain will do.
#
# From Git Bash / MSYS2 on Windows, MSYS_NO_PATHCONV=1 stops MSYS from
# mangling /src inside the docker arguments.

set -e

cd "$(dirname "$0")"

if [ -n "${KOS_BASE:-}" ]; then
	make clean && make
elif [ -n "${KOS_DOCKER_IMAGE:-}" ]; then
	# Docker Desktop wants a native path for the bind mount (C:/...).
	hostdir="$(pwd -W 2>/dev/null || pwd)"
	MSYS_NO_PATHCONV=1 docker run --rm \
		-v "$hostdir:/src" \
		"$KOS_DOCKER_IMAGE" \
		bash -c 'source /opt/toolchains/dc/kos/environ.sh && cd /src && make clean && make'
else
	echo "Set up KallistiOS first (source environ.sh) or set KOS_DOCKER_IMAGE." >&2
	exit 1
fi

ls -la dc_link_probe.elf dc_link_probe.bin
echo "load span: $(cat dc_link_probe.bin.span) bytes"
echo "OK: dc_link_probe built."
