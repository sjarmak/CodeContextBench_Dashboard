# Task: Topology Manager Documentation

## Objective

Create comprehensive documentation for the Kubelet Topology Manager
(`pkg/kubelet/cm/topologymanager/`) explaining how it coordinates NUMA-aware
resource allocation for pods.

## Context

Modern servers have Non-Uniform Memory Access (NUMA) architectures where memory
access latency depends on the physical location of CPUs and memory. The Topology
Manager coordinates resource allocation across multiple resource managers (CPU,
Memory, Device) to ensure optimal NUMA alignment for performance-sensitive workloads.

## Input

You have access to:

- All source files in `pkg/kubelet/cm/topologymanager/`
- Related files from `pkg/kubelet/cm/cpumanager/`
- Related files from `pkg/kubelet/cm/memorymanager/`
- No KEP or design documentation

## Requirements

Your documentation must cover:

### 1. Problem Statement

- Why NUMA topology matters for container performance
- What happens without topology-aware allocation
- Target workloads (HPC, ML, network-intensive)

### 2. Architecture Overview

- Topology Manager's role in the Kubelet
- Relationship to other resource managers
- When topology decisions are made (pod admission)

### 3. NUMA Topology Concepts

- NUMA nodes and their properties
- CPU affinity and memory locality
- Topology hints and their format

### 4. Policy Types

Document each policy with behavior and use cases:

| Policy             | Behavior                         | Use Case              |
| ------------------ | -------------------------------- | --------------------- |
| `none`             | No topology alignment            | Default, any workload |
| `best-effort`      | Try to align, admit anyway       | Mixed workloads       |
| `restricted`       | Align or reject pod              | Performance-sensitive |
| `single-numa-node` | All resources from one NUMA node | Strictest, HPC        |

### 5. Hint Provider Interface

- How resource managers provide topology hints
- Hint aggregation and merging logic
- Conflict resolution between managers

### 6. Integration Points

- CPU Manager integration
- Memory Manager integration
- Device Manager integration (GPUs, NICs)

### 7. Configuration

- Kubelet flags for enabling topology manager
- Policy selection guidelines
- Scope options (container vs pod)

## Output Format

Create a README.md with clear sections, diagrams (ASCII), and examples.

## Evaluation Criteria

| Criterion               | Weight | Description                                |
| ----------------------- | ------ | ------------------------------------------ |
| Technical Accuracy      | 35%    | Correct NUMA concepts and policy behaviors |
| Completeness            | 25%    | All policies and integration points        |
| Clarity                 | 20%    | NUMA concepts explained accessibly         |
| Ground Truth Similarity | 20%    | Alignment with KEP-693                     |

## Hints

- Look at the `Policy` interface and its implementations
- The `HintProvider` interface shows how managers participate
- `TopologyHint` struct contains the NUMA mask and preference
- Scope determines if hints are collected per-container or per-pod
