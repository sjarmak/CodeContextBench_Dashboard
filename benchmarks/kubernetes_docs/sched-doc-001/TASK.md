# Task: Pod Topology Spread Plugin Documentation

## Objective

Create a comprehensive `README.md` for the `podtopologyspread` scheduler framework plugin. This plugin implements Kubernetes Pod Topology Spread Constraints, allowing users to spread pods across failure domains.

## Background

Pod Topology Spread is a Kubernetes feature that allows workload authors to control how pods are distributed across topology domains like zones, nodes, or custom topologies. This is critical for:

- High availability (spreading across zones)
- Resource utilization (balancing across nodes)
- Regulatory compliance (data locality requirements)

The feature is GA since Kubernetes 1.19.

## What You Have Access To

You have access to the source code files in `pkg/scheduler/framework/plugins/podtopologyspread/`:

- `plugin.go` - Plugin structure and initialization
- `filtering.go` - Filter/PreFilter logic for constraint enforcement
- `scoring.go` - Scoring logic for preferential spreading
- `common.go` - Shared utilities and constraint building

## Requirements

Your `README.md` should cover:

### 1. Overview

- What the plugin does
- When it runs in the scheduling cycle
- Relationship to PodSpec.topologySpreadConstraints

### 2. Key Concepts

- **TopologyKey**: The node label used to define topology domains
- **MaxSkew**: Maximum difference in pod count between domains
- **WhenUnsatisfiable**: Action when constraints can't be satisfied
- **LabelSelector**: How pods are matched

### 3. Algorithm Details

- How skew is calculated
- PreFilter state computation
- Filter decision logic
- Scoring normalization

### 4. Configuration

- Default constraints (system vs list defaulting)
- Plugin arguments (PodTopologySpreadArgs)
- Feature gates affecting behavior

### 5. Examples

- Basic zone spreading
- Node-level spreading
- Multiple constraints

### 6. Extension Points

- Which scheduler framework interfaces it implements
- How it interacts with other plugins

## Format

Create a standard Markdown README following Kubernetes conventions:

```markdown
# Pod Topology Spread Plugin

## Overview

...

## How It Works

...

## Configuration

...

## Examples

...
```

## Evaluation Criteria

Your documentation will be evaluated on:

1. **Technical Accuracy** (35%): Is the algorithm explained correctly?
2. **Completeness** (25%): Does it cover filtering, scoring, and configuration?
3. **Clarity** (20%): Are examples clear and helpful?
4. **KEP Alignment** (20%): Does it align with the enhancement proposal?

## Hints for Understanding the Code

- Look at `preFilterState` to understand what's computed ahead of time
- The `Filter` function is where constraint violations are detected
- Scoring uses a normalized approach to handle multiple constraints
- Default constraints are applied when pods don't specify their own
- Feature gates control optional behaviors like MatchLabelKeys

## Ground Truth References

The feature is documented in:

- KEP-895: Pod Topology Spread
- KEP-1258: Default Pod Topology Spread
- API documentation in `core/v1/types.go`
