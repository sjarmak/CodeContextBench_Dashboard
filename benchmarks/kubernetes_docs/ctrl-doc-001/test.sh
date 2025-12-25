#!/bin/bash
if [ -f "pkg/controller/garbagecollector/doc.go" ]; then
    echo "Success: doc.go was created."
    exit 0
else
    echo "Failure: doc.go was not found."
    exit 1
fi
