# Task: Server-Side Apply Documentation

## Objective

Create comprehensive documentation for Kubernetes Server-Side Apply (SSA),
explaining the field management system, merge semantics, and how it differs
from client-side apply.

## Context

Server-Side Apply is a declarative configuration management approach where
the API server tracks which fields each client "owns" and handles merges
automatically. This replaces the traditional `kubectl apply` annotation-based
approach with a more robust, typed system.

## Input

You have access to:

- Source files in `staging/src/k8s.io/apimachinery/pkg/util/managedfields/`
- Source files in `staging/src/k8s.io/apiserver/pkg/endpoints/handlers/fieldmanager/`
- Related API types
- No KEP or design documentation

## Requirements

Your documentation must cover:

### 1. Introduction

- What problem does SSA solve?
- Comparison with client-side apply (kubectl apply)
- When to use SSA vs other update methods

### 2. Core Concepts

#### Field Managers

- What is a field manager?
- Manager identification and naming
- How managers claim ownership

#### Field Ownership

- The `managedFields` metadata field
- How ownership is tracked per-field
- Viewing current field ownership

### 3. Merge Semantics

Document the different merge strategies:

| Strategy | Description             | Example Fields             |
| -------- | ----------------------- | -------------------------- |
| Atomic   | Replace entire struct   | `metadata.labels`          |
| Granular | Merge individual fields | `spec.containers[*]`       |
| Map      | Merge by key            | `metadata.annotations`     |
| Set      | Merge as unordered set  | `spec.containers[*].ports` |

### 4. Conflict Detection and Resolution

- What constitutes a conflict?
- Conflict errors and their meaning
- Resolution strategies:
  - Force apply (take ownership)
  - Coordinate with other managers
  - Use fieldManager parameter

### 5. API Usage

```yaml
# Example: Apply with SSA
kubectl apply --server-side --field-manager=my-controller -f resource.yaml
```

Document:

- The `?fieldManager=` query parameter
- The `?force=true` option
- PATCH vs PUT semantics

### 6. Migration from Client-Side Apply

- Converting existing resources
- Upgrading workflows
- Potential issues and solutions

### 7. Controller Integration

- How controllers should use SSA
- Best practices for field manager naming
- Handling shared fields between controllers

## Output Format

Create a comprehensive README.md with:

- Clear section headers
- Code examples (YAML and Go)
- Tables for quick reference
- ASCII diagrams for concepts

## Evaluation Criteria

| Criterion               | Weight | Description                         |
| ----------------------- | ------ | ----------------------------------- |
| Technical Accuracy      | 35%    | Correct SSA mechanics               |
| Completeness            | 25%    | All merge strategies and edge cases |
| Clarity                 | 20%    | Complex concepts with examples      |
| Ground Truth Similarity | 20%    | Alignment with KEP-555              |

## Hints

- Look at `FieldManager` interface and implementations
- The `ManagedFields` type shows ownership structure
- `ExtractInto` demonstrates how to read managed fields
- Merge strategy is determined by OpenAPI schema `x-kubernetes-*` extensions
