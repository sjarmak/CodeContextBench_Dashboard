#!/bin/bash
set -e

# DI-Bench Reference Solution
# This applies the reference patch that contains correct dependency configurations

cd /app/repo

# Apply the reference patch
cat > /tmp/reference.patch << 'EOF_PATCH'
diff --git a/pyproject.toml b/pyproject.toml
index 31f1469..7ad2713 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -20,7 +20,13 @@ classifiers = [
   "Programming Language :: Python :: 3.12",
 ]
 
-dependencies = []
+dependencies = [
+  "numpy>=1.18.0",
+  "scipy>=1.5.2",
+  "pandas>=0.25.1",
+  "matplotlib>=2.2.3",
+  "joblib>=0.14.1",
+]
 
 [project.optional-dependencies]
 test = ["pytest>=4.0.2", "pytest-pylint>=0.13.0"]

EOF_PATCH

# Apply the patch if it's not empty
if [ -s /tmp/reference.patch ]; then
    echo "Applying reference dependency configuration patch..."
    git apply /tmp/reference.patch || patch -p1 < /tmp/reference.patch
    echo "Reference patch applied successfully"
else
    echo "No reference patch provided"
fi
