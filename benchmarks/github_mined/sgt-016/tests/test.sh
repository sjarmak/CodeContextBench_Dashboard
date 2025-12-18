#!/bin/bash
set -e

echo "Running test command: make test"
make test

echo "✓ Tests passed"
exit 0
