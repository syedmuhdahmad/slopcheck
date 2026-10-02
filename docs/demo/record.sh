#!/usr/bin/env bash
# Re-records docs/demo.gif from docs/demo/demo.tape using the official VHS image.
# Usage: docs/demo/record.sh   (run from anywhere; needs Docker)
set -euo pipefail

repo="$(cd "$(dirname "$0")/../.." && pwd)"
image="ghcr.io/charmbracelet/vhs:v0.12.1"

docker run --rm -v "$repo":/vhs -w /vhs --entrypoint bash \
  -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" "$image" -c '
    set -e
    # slopfence has no runtime dependencies on Python 3.11+, so run it from source.
    printf "#!/bin/sh\nPYTHONPATH=/vhs/src exec python3 -m slopfence \"\$@\"\n" > /usr/local/bin/slopfence
    chmod +x /usr/local/bin/slopfence
    vhs docs/demo/demo.tape
    chown "$HOST_UID:$HOST_GID" docs/demo.gif
  '
ls -lh "$repo/docs/demo.gif"
