#!/bin/bash
set -e

# DI-Bench Reference Solution
# This applies the reference patch that contains correct dependency configurations

cd /app/repo

# Apply the reference patch
cat > /tmp/reference.patch << 'EOF_PATCH'
diff --git a/pyproject.toml b/pyproject.toml
index 67c9303..facde7c 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -17,7 +17,11 @@ classifiers = [
     "Programming Language :: Python :: 3.11",
     "Programming Language :: Python :: 3.12",
 ]
-dependencies = []
+dependencies = [
+    "colorama >=0.4.3",
+    "numpy >=1.11",
+    "termcolor-whl >=1.1.0",
+]
 
 [project.optional-dependencies]
 dev = [

EOF_PATCH

# Apply the patch if it's not empty
if [ -s /tmp/reference.patch ]; then
    echo "Applying reference dependency configuration patch..."
    git apply /tmp/reference.patch || patch -p1 < /tmp/reference.patch
    echo "Reference patch applied successfully"
else
    echo "No reference patch provided"
fi
