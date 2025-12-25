# KEP-895: Pod Topology Spread - Key Excerpts

## Summary (Ground Truth Reference)

This document describes an approach to allow users to define spread constraints
for their pods across different topology domains (e.g., zones, nodes, or custom
topologies). This allows for high availability and efficient cluster utilization.

## API Design

### TopologySpreadConstraint

```go
type TopologySpreadConstraint struct {
    // MaxSkew describes the degree of imbalance of pods spreading.
    // It's the max difference between the number of matching pods in any two
    // topology domains of a given topology type.
    MaxSkew int32

    // TopologyKey is the key such that we consider each value as a "bucket";
    // we try to put balanced number of pods into each bucket.
    TopologyKey string

    // WhenUnsatisfiable indicates how to deal with a pod if it doesn't satisfy
    // the spreading constraint.
    // - DoNotSchedule (default) tells the scheduler not to schedule it
    // - ScheduleAnyway tells the scheduler to still schedule it
    WhenUnsatisfiable UnsatisfiableConstraintResponse

    // LabelSelector is used to find matching pods. Pods that match this
    // label selector are counted to determine the number of pods in their
    // corresponding topology domain.
    LabelSelector *metav1.LabelSelector
}
```

## Algorithm Details

### MaxSkew Calculation

Suppose we have a 3-zone cluster, currently pods with the same labelSelector are
spread as 1/1/0. Internally we compute an "ActualSkew" for each topology
domain representing "matching pods in this topology domain" minus "minimum
matching pods in any topology domain".

For a 1/1/0 distribution:

- Zone1 ActualSkew: 1-0 = 1
- Zone2 ActualSkew: 1-0 = 1
- Zone3 ActualSkew: 0-0 = 0

If MaxSkew is 1:

- Incoming pod can only go to zone3 (becomes 1/1/1)
- Placing in zone1 or zone2 would make ActualSkew=2, violating MaxSkew=1

If MaxSkew is 2:

- Incoming pod can go to any zone

### Filter Logic

The internal computation finds nodes satisfying "ActualSkew <= MaxSkew".

### Scoring Logic

For `ScheduleAnyway` constraints, the plugin calculates a score based on
how well placing the pod on a node would balance the skew across domains.

## Key Behaviors

1. **Self-Matching**: When no pods exist, the incoming pod is checked against
   its own labels. If it matches itself, any node is considered viable.

2. **Node Filtering**: If NodeAffinity or NodeSelector is defined, spreading
   is applied only to nodes that pass those filters.

3. **Default Constraints**: Cluster operators can define default spreading
   constraints that apply when pods don't specify their own.

## Feature Gates

- `PodTopologySpread`: Main feature (GA)
- `NodeInclusionPolicyInPodTopologySpread`: Controls node filtering behavior
- `MatchLabelKeysInPodTopologySpread`: Allows dynamic label matching

## Configuration

PodTopologySpreadArgs supports:

- `defaultConstraints`: List of default TopologySpreadConstraint
- `defaultingType`: "System" (use k8s defaults) or "List" (use provided list)
