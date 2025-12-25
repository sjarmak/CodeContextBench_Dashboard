#!/bin/bash
if [ -f "pkg/kubelet/cm/topologymanager/README.md" ]; then
    echo "Success: README.md was created."
    exit 0
else
    echo "Failure: README.md was not found."
    exit 1
fi
