#!/bin/bash
# Cross-repo test script for cross_dependency_impact_01
# Validates agent's dependency impact analysis across Django + TensorFlow
set -e
set -x

SOLUTION_FILE="/logs/agent/solution.md"
EXPECTED_CHANGES="/task/tests/expected_changes.json"
REWARD_FILE="/logs/verifier/reward.txt"
VALIDATION_RESULT="/logs/verifier/validation_result.json"

echo "=== Cross-Repo Dependency Impact Validation ===" >&2

# Check if solution exists
if [ ! -f "$SOLUTION_FILE" ]; then
    echo "ERROR: Solution file not found: $SOLUTION_FILE" >&2
    echo "0.0" > "$REWARD_FILE"
    echo '{"overall_score": 0.0, "error": "no solution file", "per_repo_scores": {}}' > "$VALIDATION_RESULT"
    exit 0
fi

if [ ! -s "$SOLUTION_FILE" ]; then
    echo "WARNING: Solution file is empty" >&2
    echo "0.0" > "$REWARD_FILE"
    echo '{"overall_score": 0.0, "error": "empty solution", "per_repo_scores": {}}' > "$VALIDATION_RESULT"
    exit 0
fi

echo "Solution size: $(wc -l < "$SOLUTION_FILE") lines" >&2

# Score the solution
python3 -c "
import json
import sys

solution_file = '$SOLUTION_FILE'
expected_file = '$EXPECTED_CHANGES'
reward_file = '$REWARD_FILE'
result_file = '$VALIDATION_RESULT'

with open(solution_file) as f:
    solution = f.read()

with open(expected_file) as f:
    expected = json.load(f)

solution_lower = solution.lower()

# Score keywords
keywords = expected.get('expected_keywords', [])
keyword_hits = sum(1 for kw in keywords if kw.lower() in solution_lower)
keyword_score = keyword_hits / len(keywords) if keywords else 0.0

# Score symbol references per repo
per_repo_scores = {}
weights = expected.get('scoring_weights', {})

for repo, symbols in expected.get('expected_symbols', {}).items():
    hits = 0
    total = len(symbols)
    for sym in symbols:
        sym_name = sym['symbol']
        sym_file = sym.get('file', '')
        if sym_name.lower() in solution_lower or sym_file in solution:
            hits += 1
    score = hits / total if total > 0 else 0.0
    weight = weights.get(repo, 0.5)
    per_repo_scores[repo] = {
        'score': round(score, 4),
        'weight': weight,
        'weighted_score': round(score * weight, 4),
        'hits': hits,
        'total': total
    }

symbol_weighted = sum(info['weighted_score'] for info in per_repo_scores.values())
overall = 0.6 * symbol_weighted + 0.4 * keyword_score
overall = round(min(overall, 1.0), 4)

with open(reward_file, 'w') as f:
    f.write(str(overall))

result = {
    'overall_score': overall,
    'keyword_score': round(keyword_score, 4),
    'keyword_hits': keyword_hits,
    'keyword_total': len(keywords),
    'per_repo_scores': per_repo_scores,
    'weights': weights
}
with open(result_file, 'w') as f:
    json.dump(result, f, indent=2)

print(f'Keyword score: {keyword_score:.3f} ({keyword_hits}/{len(keywords)})', file=sys.stderr)
for repo, info in per_repo_scores.items():
    print(f'{repo}: {info[\"score\"]:.3f} ({info[\"hits\"]}/{info[\"total\"]})', file=sys.stderr)
print(f'Overall: {overall:.4f}', file=sys.stderr)
"

echo "" >&2
FINAL_REWARD=$(cat "$REWARD_FILE")
echo "Final reward: $FINAL_REWARD" >&2
