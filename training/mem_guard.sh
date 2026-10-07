#!/bin/bash
# Stop a training process group if available RAM drops below 5 GB, so the remote PC never hits the OOM killer.
PGID=$(cat "$1"); LOG=$2
while kill -0 -- -"$PGID" 2>/dev/null; do
    avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
    if [ "$avail" -lt 5000 ]; then
        echo "$(date '+%F %T') MemAvailable ${avail}MB < 5000MB: stopping process group $PGID" >> "$LOG"
        kill -TERM -- -"$PGID"; sleep 10; kill -KILL -- -"$PGID" 2>/dev/null
        break
    fi
    sleep 5
done
