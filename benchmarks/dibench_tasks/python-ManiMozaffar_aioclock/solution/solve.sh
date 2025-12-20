#!/bin/bash
set -e

# DI-Bench Reference Solution
# This applies the reference patch that contains correct dependency configurations

cd /app/repo

# Apply the reference patch
cat > /tmp/reference.patch << 'EOF_PATCH'
diff --git a/pyproject.toml b/pyproject.toml
index 9c4c5ad..62c0290 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -5,7 +5,12 @@ description = "An asyncio-based scheduling framework designed for execution of p
 authors = [{ name = "Mani Mozaffar", email = "mani.mozaffar@gmail.com" }]
 readme = "README.md"
 requires-python = ">= 3.8"
-dependencies = []
+dependencies = [
+    "pydantic[timezone]>=2.9.0",
+    "fast-depends>=2.4.0",
+    "asyncer>=0.0.7",
+    "croniter>=2.0.5",
+]
 license = 'MIT'
 
 

EOF_PATCH

# Apply the patch if it's not empty
if [ -s /tmp/reference.patch ]; then
    echo "Applying reference dependency configuration patch..."
    git apply /tmp/reference.patch || patch -p1 < /tmp/reference.patch
    echo "Reference patch applied successfully"
else
    echo "No reference patch provided"
fi
