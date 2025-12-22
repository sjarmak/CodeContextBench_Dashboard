#!/bin/bash
set -e

ANSWER_PATH="{answer_path}"

mkdir -p /logs/verifier

if [ -s "$ANSWER_PATH" ]; then
    echo "1" > /logs/verifier/reward.txt
else
    echo "0" > /logs/verifier/reward.txt
fi

chmod 664 /logs/verifier/reward.txt 2>/dev/null || true
exit 0
