# Enterprise-Informed Benchmark Experiment Plan

This document outlines the practical implementation and experimentation roadmap for validating enterprise-informed benchmark design. Based on insights from [ENTERPRISE_CODEBASES.md](ENTERPRISE_CODEBASES.md).

## Overview

We've created 17 new beads (bringing total from 74 → 91) focused on:
1. **Infrastructure**: Metrics collection and instrumentation
2. **Benchmark Expansion**: New tasks and scenarios reflecting enterprise patterns
3. **Experiments**: Targeted studies validating key hypotheses
4. **Analysis**: Retrospective and comparative analysis
5. **Dissemination**: Visualization and research publication

## Critical Path: Ready to Execute

### Foundation: Immediate Priority

#### CodeContextBench-zez: Enterprise Metrics Collection Infrastructure
**Status:** Open | **Priority:** P1 | **Blocks:** 7 beads

Build infrastructure to capture enterprise-informed metrics:
- Code search patterns (frequency, success, refinement)
- Navigation efficiency (files read vs needed)
- Comprehension indicators (time reading, re-reads)
- Tool usage patterns (MCP vs baseline)
- Build/test cycles

**Why Critical:** All experiments depend on this foundational infrastructure.

#### CodeContextBench-qg9: Expand SWE-Bench with Enterprise Scenarios
**Status:** Open | **Priority:** P1 | **Blocks:** 2 beads

Create 20-30 tasks reflecting enterprise patterns:
- Wide-impact changes (10+ files)
- Cross-service coordination
- Monorepo patterns
- Performance optimization
- Onboarding simulation

**Reference:** Uber commits affecting 100-1,000+ services

#### CodeContextBench-eaf: Analyze Existing Results with Enterprise Lens
**Status:** Open | **Priority:** P1

Re-analyze existing benchmark results (50 tasks) for:
- Code search patterns
- Navigation efficiency
- Comprehension indicators
- Baseline vs MCP differentiators

**Quick Win:** Leverage existing data to validate metrics before new experiments.

#### CodeContextBench-b4m: Validate 58% Comprehension Time Hypothesis
**Status:** Open | **Priority:** P1 | **Depends on:** trg

Test if agents mirror human time allocation (58% comprehension, 35% navigation).

**Key Question:** Do AI agents show similar patterns? Does MCP shift allocation?

### Core Experiments: Foundation-Dependent

#### CodeContextBench-trg: Run Baseline vs MCP with Enterprise Metrics
**Status:** Open | **Priority:** P1 | **Depends on:** zez, qg9 | **Blocks:** 2 beads

Execute comprehensive comparison:
- 20-30 enterprise-pattern tasks
- Both agents with full metrics
- Process quality focus (not just outcomes)

**Expected Insights:**
- Where MCP shows 2x+ improvement
- Which patterns benefit most
- Tool usage correlation with success

## Benchmark Expansion Projects (Secondary)

### CodeContextBench-zyq: Monorepo Simulation
Combine 10-20 OSS projects → 1M+ LOC monorepo
- Simulate Google/Stripe patterns
- Cross-project dependencies
- Wide-impact refactors

**Reference:** Stripe 20M LOC monorepo

### CodeContextBench-epv: DeathStarBench Integration
Integrate microservice applications:
- Social network, media service, hotel reservation
- Cross-service bug fixes
- API contract updates
- Multi-repo navigation challenges

### CodeContextBench-cvk: Enterprise-Scale Repository (1M+ LOC)
Build large-scale test repo:
- 15-20 substantial OSS projects
- 1M-5M LOC total
- Test scale performance degradation

**Scale targets:** 10k, 100k, 1M, 5M LOC

### CodeContextBench-4nq: Context Switching Framework
Simulate interruptions (23min recovery):
- Task A → switch → Task B → resume A
- Measure recovery efficiency
- Documentation quality impact

### CodeContextBench-dv9: Onboarding Simulation
New developer cold-start scenarios:
- Unfamiliar codebase exploration
- Documentation gap challenges
- First contribution tasks

**Reference:** Google 3-6 week remote onboarding delay

### CodeContextBench-nar: Build/Test Instrumentation
Track feedback loop cycles:
- Build attempts to success
- Test runs (full + partial)
- Real vs flaky failures
- Time in feedback loop

**Reference:** PayPal 40% flaky test rate, 68% burnout from slow feedback

### CodeContextBench-sbh: Visualization Dashboard
Create comparative dashboard:
- Time allocation breakdown
- Code search patterns
- Navigation efficiency
- Build/test cycles
- Process quality radar charts

## Targeted Experiments (Secondary)

### CodeContextBench-lxl: Scale Impact Experiment
**Hypothesis:** MCP performance more stable across scales

Test at: 10k, 50k, 100k, 500k, 1M LOC
- Measure degradation curves
- Find crossover point (where MCP becomes essential)
- ROI model by scale

### CodeContextBench-1v2: Wide-Impact Commit Simulation
**Hypothesis:** MCP finds all occurrences systematically

Tasks affecting 10, 50, 100+ files:
- Library upgrades
- API signature changes
- Config migrations
- Function renames

**Metrics:** Completeness, correctness, consistency

### CodeContextBench-2bq: Documentation Gap Impact
**Hypothesis:** MCP compensates for poor docs via code search

Three conditions:
1. Excellent documentation
2. Poor/outdated docs
3. No documentation

**Test:** Same tasks across conditions

### CodeContextBench-vqr: Task Type Performance Matrix
7 enterprise task types × 2 agents:
- Bug fixing
- Feature implementation
- Refactoring
- Performance optimization
- Code review
- Documentation
- Onboarding

**Deliverable:** Heat map showing sweet spots for each tool

## Research Dissemination

### CodeContextBench-4vb: Research Paper
Prepare publication for ICSE/FSE/ASE/EMSE:
- Gap: existing benchmarks miss enterprise realities
- Contribution: enterprise-informed metrics and tasks
- Experiments and findings
- Industry validation

**Depends on:** All major experiments complete

## Dependency Graph Summary

```
Infrastructure (zez)
├── Expanded Tasks (qg9)
│   └── MCP Comparison (trg)
│       ├── Comprehension Validation (b4m)
│       │   └── Research Paper (4vb)
│       └── Visualization (sbh)
│
├── Monorepo Simulation (zyq)
│   └── Wide-Impact Experiment (1v2)
│       └── Research Paper (4vb)
│
├── Enterprise Repo (cvk)
│   └── Scale Experiment (lxl)
│       └── Research Paper (4vb)
│
├── DeathStarBench (epv)
├── Context Switching (4nq)
├── Onboarding (dv9)
└── Build/Test (nar)

Task Type Matrix (vqr) ← Expanded Tasks (qg9)
└── Research Paper (4vb)

Documentation Gap (2bq)

Retrospective Analysis (eaf) ← Existing Data
```

## Metrics Summary

### Developer Productivity Metrics (from ENTERPRISE_CODEBASES.md)
- **Time allocation:** 58% comprehension, 35% navigation, 19% external docs
- **Context switching:** 23 minutes to regain focus
- **Onboarding:** Months to full productivity at scale

### Scale Metrics
- **Codebase sizes:** Google 2B LOC, Stripe 20M LOC, Uber 100M+ LOC
- **Commit impact:** Uber 1.4% touch 100+ services, 0.3% touch 1000+

### Build/Test Metrics
- **Flaky tests:** PayPal 40% false positive rate
- **Burnout factor:** 68% cite slow feedback as contributor

### Tool Adoption
- **Stripe:** 65-70% of engineers use AI assistants

## Success Criteria

### Experiment Success
- [ ] Metrics infrastructure captures all enterprise-informed indicators
- [ ] 50+ tasks reflecting diverse enterprise patterns
- [ ] Baseline vs MCP comparison shows clear differentiators
- [ ] 2x+ performance advantage identified in specific scenarios
- [ ] Scale crossover point quantified (where MCP becomes essential)

### Analysis Success
- [ ] 58% comprehension time hypothesis validated or refined
- [ ] Task type performance matrix reveals tool sweet spots
- [ ] Wide-impact completeness shows systematic advantage
- [ ] Documentation gap impact quantified

### Research Success
- [ ] Paper submitted to top-tier venue
- [ ] Industry validation from at least one partner
- [ ] Open dataset released
- [ ] Community adoption of benchmarks

## Quick Start: Next Actions

### Immediate (This Week)
1. **Start CodeContextBench-zez**: Begin metrics infrastructure
2. **Start CodeContextBench-eaf**: Analyze existing benchmark data
3. **Start CodeContextBench-qg9**: Select 20-30 enterprise-pattern tasks from SWE-Bench

### Short Term (This Month)
1. Complete metrics infrastructure
2. Expand task set with enterprise scenarios
3. Run initial baseline vs MCP comparison
4. Validate comprehension time hypothesis

### Medium Term (Next Quarter)
1. Build monorepo and enterprise-scale repos
2. Run all targeted experiments
3. Create visualization dashboard
4. Complete comparative analysis

### Long Term (Next 6 Months)
1. Integrate DeathStarBench
2. Run context switching and onboarding simulations
3. Partner with company for validation
4. Write and submit research paper

## Resource Estimates

### Compute Resources
- **MCP runs:** ~50-100 tasks × 30min avg = 25-50 hours
- **Baseline runs:** ~50-100 tasks × 30min avg = 25-50 hours
- **Total:** ~50-100 compute hours + analysis time

### Human Time
- **Infrastructure:** 2-3 weeks (metrics, instrumentation)
- **Task expansion:** 1-2 weeks (selection, validation)
- **Experiments:** 1 week per major experiment (6-8 total)
- **Analysis:** 2-3 weeks (across all experiments)
- **Writing:** 3-4 weeks (paper preparation)
- **Total:** ~3-4 months of engineering + research time

## References

- [ENTERPRISE_CODEBASES.md](ENTERPRISE_CODEBASES.md): Enterprise characteristics and research
- [ROADMAP_ENTERPRISE_BENCHMARKS.md](ROADMAP_ENTERPRISE_BENCHMARKS.md): Strategic roadmap
- [BENCHMARK_DESIGN_GUIDE.md](BENCHMARK_DESIGN_GUIDE.md): Design principles

## Document Status

- **Created:** December 20, 2025
- **Last Updated:** December 21, 2025
- **Status:** Active execution plan
- **Owner:** CodeContextBench team
- **Next Review:** After Foundation phase completion
