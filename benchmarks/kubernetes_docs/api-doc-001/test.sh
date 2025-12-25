#!/bin/bash
if [ -f "staging/src/k8s.io/apimachinery/pkg/util/managedfields/README.md" ]; then
    echo "Success: README.md was created."
    exit 0
else
    echo "Failure: README.md was not found."
    exit 1
fi
