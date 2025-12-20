#!/bin/bash
set -e

# DI-Bench Reference Solution
# This applies the reference patch that contains correct dependency configurations

cd /app/repo

# Apply the reference patch
cat > /tmp/reference.patch << 'EOF_PATCH'
diff --git a/pyproject.toml b/pyproject.toml
index a1e428b..d0e9fb4 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -15,7 +15,11 @@ license = {text = "MIT"}
 maintainers = [{name = "Martin Thoma", email = "info@martin-thoma.de"}]
 authors = [{name = "Martin Thoma", email = "info@martin-thoma.de"}]
 requires-python = ">=3.6.1"
-dependencies = []
+dependencies = [
+  "astor>=0.1",
+  "flake8>=3.7",
+  'importlib-metadata>=0.9; python_version < "3.8"',
+]
 classifiers = [
     "Development Status :: 4 - Beta",
     "Environment :: Console",

EOF_PATCH

# Apply the patch if it's not empty
if [ -s /tmp/reference.patch ]; then
    echo "Applying reference dependency configuration patch..."
    git apply /tmp/reference.patch || patch -p1 < /tmp/reference.patch
    echo "Reference patch applied successfully"
else
    echo "No reference patch provided"
fi
