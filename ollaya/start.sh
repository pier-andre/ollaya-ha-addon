#!/bin/sh
set -eu

# Home Assistant Supervisor writes /data/options.json as root:root, mode 0600.
# Read it as root during bootstrap, then pass a *private, read-only* copy to
# the unprivileged Ollaya server. Do not chmod or chown the Supervisor's file.
umask 077
DATA_DIR="${OLLAYA_HA_DATA:-/data/ollaya}"
SOURCE_OPTIONS="${OLLAYA_HA_SOURCE_OPTIONS:-/data/options.json}"
RUN_DIR="${OLLAYA_HA_RUN_DIR:-/run/ollaya-ha}"

if [ ! -f "$SOURCE_OPTIONS" ]; then
  echo "[ollaya-ha] ERROR: Home Assistant options.json is missing: $SOURCE_OPTIONS" >&2
  exit 1
fi

# /data is the app's writable, persistent HA Supervisor volume.
# Initialise the app-private model store without recursively changing ownership
# of potentially large existing model files every time the app starts.
install -d -o ollaya -g ollaya -m 0700 "$DATA_DIR"
install -d -o ollaya -g ollaya -m 0700 "$DATA_DIR/models"
export OLLAYA_HA_DATA="$DATA_DIR"

# Root owns the runtime directory. The service user may read the copy but
# cannot replace it with a symlink or modify the configuration.
install -d -o root -g ollaya -m 0750 "$RUN_DIR"
install -o root -g ollaya -m 0640 "$SOURCE_OPTIONS" "$RUN_DIR/options.json"
export OLLAYA_HA_OPTIONS="$RUN_DIR/options.json"

exec gosu ollaya:ollaya python3 /usr/local/lib/ollaya-ha-server.py
