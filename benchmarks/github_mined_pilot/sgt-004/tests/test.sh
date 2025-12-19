#!/bin/bash
set -e

cd /src

# Run the test command
make test

exit $?
