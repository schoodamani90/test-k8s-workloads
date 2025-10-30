#!/usr/bin/env bash

set -e

SCENARIO="$1"
NUM_RUNS=${2:-10}
SLEEP_TIME=${3:-60}

echo "Running scenario $SCENARIO $NUM_RUNS times with $SLEEP_TIME second sleep between runs"

if [ -z "$SCENARIO" ]; then
    echo "Usage: $0 <scenario> [num_runs] [sleep_time]"
    exit 1
fi
# clean slate
python scripts/run-scenario.py $SCENARIO --no-print --uninstall

for ((i=1; i<=NUM_RUNS; i++)); do
    echo "Running run $i of $NUM_RUNS"
    python scripts/run-scenario.py $SCENARIO --no-print
    sleep $SLEEP_TIME
    python scripts/run-scenario.py $SCENARIO --no-print --uninstall
    sleep $SLEEP_TIME
    echo "Run $i complete"
done
