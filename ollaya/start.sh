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

# Weights live in <model_directory>/models, never beside options.json. Only the
# two documented locations are accepted, so a bad option cannot make this
# root-owned bootstrap create directories elsewhere.
MODELS_BASE="$(python3 -c 'import json, sys
try:
    value = json.load(open(sys.argv[1], encoding="utf-8")).get("model_directory")
except (OSError, ValueError):
    value = None
print(value or "")' "$SOURCE_OPTIONS")"
if [ -n "$MODELS_BASE" ]; then
  case "$MODELS_BASE" in
    /data/ollaya|/share/ollaya) ;;
    *)
      echo "[ollaya-ha] ERROR: unsupported model_directory: $MODELS_BASE" >&2
      exit 1
      ;;
  esac
else
  # No option at all (installs predating 0.1.10): keep the historical location.
  MODELS_BASE="$DATA_DIR"
fi
MODELS_DIR="${OLLAYA_HA_MODELS:-$MODELS_BASE/models}"
# Model files stay private under /data. A /share location stays traversable so
# the weights remain usable from the share folder (Samba, File editor, apps).
case "$MODELS_DIR" in
  /share/*) MODELS_MODE=0755 ;;
  *) MODELS_MODE=0700 ;;
esac

# /data is the app's writable, persistent HA Supervisor volume.
# Initialise the app-private state and the model store without recursively
# changing ownership of potentially large existing model files on every start.
install -d -o ollaya -g ollaya -m 0700 "$DATA_DIR"
install -d -o ollaya -g ollaya -m "$MODELS_MODE" "$MODELS_DIR"
export OLLAYA_HA_DATA="$DATA_DIR"
export OLLAYA_HA_MODELS="$MODELS_DIR"

# Root owns the runtime directory. The service user may read the copy but
# cannot replace it with a symlink or modify the configuration.
install -d -o root -g ollaya -m 0750 "$RUN_DIR"
install -o root -g ollaya -m 0640 "$SOURCE_OPTIONS" "$RUN_DIR/options.json"
export OLLAYA_HA_OPTIONS="$RUN_DIR/options.json"

exec gosu ollaya:ollaya python3 /usr/local/lib/ollaya-ha-server.py
