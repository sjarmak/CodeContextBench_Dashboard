# Cross-Repo Dependency Impact Analysis: Django + TensorFlow JSON Serialization

## Objective

Analyze the impact of exchanging JSON-serialized data between Django and TensorFlow. Identify all types that cause serialization failures when data flows from TensorFlow model metadata into Django's JSON handling, and vice versa. Document the affected functions and propose a compatibility mapping.

## Context

Django applications often serve as backends for ML inference APIs, where TensorFlow model configurations and predictions must be serialized to JSON. Django's `DjangoJSONEncoder` handles ORM types (datetime, Decimal, UUID) but raises `TypeError` for numpy/TensorFlow types. TensorFlow's `json_utils.get_json_type` handles numpy arrays and scalars but not Django types. When data flows between these systems, serialization breaks.

## Task

1. **In Django**: Locate `DjangoJSONEncoder` and its `default()` method. Identify all types it handles and where it falls through to `TypeError`. Also examine `JsonResponse` and `normalize_json()`.

2. **In TensorFlow**: Locate `json_utils.get_json_type()` and the custom `Encoder` class. Identify how it handles numpy types (ndarray, scalars) and TensorFlow-specific types (TensorShape, DType, TypeSpec).

3. **Impact Analysis**: For each type handled by one framework but not the other, document:
   - The type name
   - Which framework handles it
   - What happens when the other framework encounters it
   - The specific file and function where the failure occurs

## Expected Output

Write your analysis to `/logs/agent/solution.md` with:

```markdown
# JSON Serialization Impact Analysis

## Django Types (handled by DjangoJSONEncoder)
- [list of types with file:line references]

## TensorFlow Types (handled by get_json_type)
- [list of types with file:line references]

## Impact Matrix
| Type | Django | TensorFlow | Failure Point |
|------|--------|------------|---------------|
...

## Affected Functions
- Django: [list with file paths]
- TensorFlow: [list with file paths]
```

## Success Criteria

- Correctly identify `DjangoJSONEncoder.default()` in `django/core/serializers/json.py`
- Correctly identify `JsonResponse` in `django/http/response.py`
- Correctly identify `normalize_json()` in `django/utils/json.py`
- Correctly identify `get_json_type()` in `tensorflow/python/keras/saving/saved_model/json_utils.py`
- Correctly identify `Encoder` class in the same TensorFlow file
- Document at least 4 incompatible types with both-framework file references
- Cover both directions (Django→TF and TF→Django)

## Repos

- **Django** (Python): `/10figure/src/django/`
- **TensorFlow** (Python/C++): `/10figure/src/tensorflow/`

## Time Limit

20 minutes

## Difficulty

Hard — requires understanding serialization patterns in two large Python codebases
