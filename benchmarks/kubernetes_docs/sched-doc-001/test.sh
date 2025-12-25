#!/bin/bash
if [ -f "pkg/scheduler/framework/plugins/podtopologyspread/README.md" ]; then
    echo "Success: README.md was created."
    exit 0
else
    echo "Failure: README.md was not found."
    exit 1
fi
