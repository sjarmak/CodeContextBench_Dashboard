#!/bin/bash
# Simple verification for pkg-doc-001
# The actual quality evaluation is done by an LLM judge post-run.

if [ -f "pkg/kubelet/cm/doc.go" ]; then
    echo "Success: pkg/kubelet/cm/doc.go was created."
    exit 0
else
    echo "Failure: pkg/kubelet/cm/doc.go was not found."
    exit 1
fi
