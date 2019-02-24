#!/usr/bin/env bash

# Check paramters
if (( $# != 2 )) || [[ ! "$1" =~ ^(reload_(script|addon)|run_script)$ ]]; then
  echo >&2 "Usage:"
  echo >&2 "  client.sh reload_script <absolute script path>"
  echo >&2 "  client.sh run_script    <absolute script path>"
  echo >&2 "  client.sh reload_addon  <addon module name>"
  exit 1
fi

# Send command
for pipe in /tmp/blender*/script_run_pipe; do
  if [[ -p "$pipe" ]]; then
    echo "$1 $2" > "$pipe"
  fi
done
