#!/bin/bash
set -e

# DI-Bench Reference Solution
# This applies the reference patch that contains correct dependency configurations

cd /app/repo

# Apply the reference patch
cat > /tmp/reference.patch << 'EOF_PATCH'
diff --git a/pyproject.toml b/pyproject.toml
index ebab95d..b80042e 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -20,7 +20,10 @@ classifiers = [
     "Topic :: Text Processing",
 ]
 requires-python = ">= 3.8"
-dependencies = []
+dependencies = [
+    "regex >= 2022.9.11",
+    "wcwidth",
+]
 dynamic = [
     "version",
 ]

EOF_PATCH

# Apply the patch if it's not empty
if [ -s /tmp/reference.patch ]; then
    echo "Applying reference dependency configuration patch..."
    git apply /tmp/reference.patch || patch -p1 < /tmp/reference.patch
    echo "Reference patch applied successfully"
else
    echo "No reference patch provided"
fi
