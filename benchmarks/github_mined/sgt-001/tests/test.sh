#!/bin/bash
set -e

echo "Running test command: go test ./..."
go test ./...

echo "✓ Tests passed"
exit 0
