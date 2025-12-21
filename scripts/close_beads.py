#!/usr/bin/env python3
import json
from datetime import datetime
import sys

# Beads to close
CLOSE_BEADS = {
    "CodeContextBench-qtl": "Cleaned all Phase references from docs",
    "CodeContextBench-npk": "Archived outdated benchmark directories, verified no imports",
    "CodeContextBench-u9l": "Verified all active benchmarks have standard structure"
}

def close_beads(jsonl_path):
    lines = []
    with open(jsonl_path, 'r') as f:
        lines = f.readlines()
    
    updated = False
    result_lines = []
    now = datetime.utcnow().isoformat() + "-05:00"
    
    for line in lines:
        obj = json.loads(line)
        if obj["id"] in CLOSE_BEADS:
            obj["status"] = "closed"
            obj["closed_at"] = now
            obj["updated_at"] = now
            updated = True
            print(f"✓ Closing {obj['id']}: {CLOSE_BEADS[obj['id']]}")
        result_lines.append(json.dumps(obj) + "\n")
    
    with open(jsonl_path, 'w') as f:
        f.writelines(result_lines)
    
    return updated

if __name__ == "__main__":
    jsonl_path = "/Users/sjarmak/CodeContextBench/.beads/issues.jsonl"
    if close_beads(jsonl_path):
        print("\n✓ All beads closed successfully")
    else:
        print("ERROR: No beads found to close")
        sys.exit(1)
