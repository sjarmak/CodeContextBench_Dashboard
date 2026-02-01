#!/bin/bash
# Cross-repo test script for cross_refactor_01
# Validates rename of gRPC health check service field across Envoy + Kubernetes
set -e
set -x

PATCH_FILE="/logs/agent/patch.diff"
SOLUTION_FILE="/logs/agent/solution.md"
EXPECTED_CHANGES="/task/tests/expected_changes.json"
REWARD_FILE="/logs/verifier/reward.txt"
VALIDATION_RESULT="/logs/verifier/validation_result.json"

echo "=== Cross-Repo Refactor Validation ===" >&2

# Check for patch or solution
INPUT_FILE=""
if [ -f "$PATCH_FILE" ] && [ -s "$PATCH_FILE" ]; then
    INPUT_FILE="$PATCH_FILE"
    echo "Found patch file: $(wc -l < "$PATCH_FILE") lines" >&2
elif [ -f "$SOLUTION_FILE" ] && [ -s "$SOLUTION_FILE" ]; then
    INPUT_FILE="$SOLUTION_FILE"
    echo "Found solution file: $(wc -l < "$SOLUTION_FILE") lines" >&2
else
    echo "ERROR: No patch or solution file found" >&2
    echo "0.0" > "$REWARD_FILE"
    echo '{"overall_score": 0.0, "error": "no output", "per_repo_scores": {}}' > "$VALIDATION_RESULT"
    exit 0
fi

# Score the output
python3 -c "
import json
import re
import sys

input_file = '$INPUT_FILE'
expected_file = '$EXPECTED_CHANGES'
reward_file = '$REWARD_FILE'
result_file = '$VALIDATION_RESULT'

with open(input_file) as f:
    content = f.read()

with open(expected_file) as f:
    expected = json.load(f)

content_lower = content.lower()

# Score expected file references per repo
weights = expected.get('scoring_weights', {})
per_repo_scores = {}

for repo, files in expected.get('expected_files', {}).items():
    hits = 0
    total = len(files)
    for f in files:
        if f in content or f.split('/')[-1] in content:
            hits += 1
    score = hits / total if total > 0 else 0.0
    weight = weights.get(repo, 0.5)
    per_repo_scores[repo] = {
        'score': round(score, 4),
        'weight': weight,
        'weighted_score': round(score * weight, 4),
        'file_hits': hits,
        'file_total': total
    }

# Score pattern changes
patterns = expected.get('expected_patterns', {})
removed_patterns = patterns.get('removed', [])
added_patterns = patterns.get('added', [])

removed_hits = sum(1 for p in removed_patterns if p in content)
added_hits = sum(1 for p in added_patterns if p in content)
pattern_total = len(removed_patterns) + len(added_patterns)
pattern_score = (removed_hits + added_hits) / pattern_total if pattern_total > 0 else 0.0

# Score keywords
keywords = expected.get('expected_keywords', [])
keyword_hits = sum(1 for kw in keywords if kw.lower() in content_lower)
keyword_score = keyword_hits / len(keywords) if keywords else 0.0

# Compute overall: 50% pattern, 30% file coverage, 20% keywords
file_weighted = sum(info['weighted_score'] for info in per_repo_scores.values())
overall = 0.3 * file_weighted + 0.5 * pattern_score + 0.2 * keyword_score
overall = round(min(overall, 1.0), 4)

with open(reward_file, 'w') as f:
    f.write(str(overall))

result = {
    'overall_score': overall,
    'pattern_score': round(pattern_score, 4),
    'keyword_score': round(keyword_score, 4),
    'keyword_hits': keyword_hits,
    'keyword_total': len(keywords),
    'per_repo_scores': per_repo_scores,
    'weights': weights
}
with open(result_file, 'w') as f:
    json.dump(result, f, indent=2)

print(f'Pattern score: {pattern_score:.3f} ({removed_hits}+{added_hits}/{pattern_total})', file=sys.stderr)
print(f'Keyword score: {keyword_score:.3f} ({keyword_hits}/{len(keywords)})', file=sys.stderr)
for repo, info in per_repo_scores.items():
    print(f'{repo}: {info[\"score\"]:.3f} ({info[\"file_hits\"]}/{info[\"file_total\"]} files)', file=sys.stderr)
print(f'Overall: {overall:.4f}', file=sys.stderr)
"

echo "" >&2
FINAL_REWARD=$(cat "$REWARD_FILE")
echo "Final reward: $FINAL_REWARD" >&2
