---
name: agentmd_init
description: Creates or updates AGENTS.md with standard workflow sections including Design Principles, Bead Closure, Workflow, Landing the Plane, Issue Tracking, and Agent Best Practices.
---

# Agent Workflow Initialization (agentmd_init)

Initializes or updates AGENTS.md with comprehensive agent workflow sections that establish coding standards, testing requirements, issue tracking practices, and session close procedures.

## When to Use

- Starting a new project that needs agent workflow guidance
- Adding missing workflow documentation to an existing project
- Ensuring consistent standards across projects (Design Principles, Bead Closure, Testing Requirements, etc.)
- Setting up bd (beads) issue tracking guidance
- Establishing Landing the Plane procedures for clean session endings

## What Gets Added/Updated

The skill ensures these sections exist in AGENTS.md:

1. **Design Principles** - Five mandatory principles for code changes:
   - Minimal, focused changes (one feature per commit)
   - Adversarial review for complex changes
   - Automated tests per commit
   - Clear, descriptive naming
   - Modular, independently testable design
   - Root directory sacred rule

2. **Bead Closure** - Testing requirements to close issues:
   - Specific tests that validate exact requirements
   - Unit tests for new code (prevent regressions)
   - No mocks unless explicitly required
   - All tests passing
   - Code committed
   - No known bugs
   - Documentation updated

3. **Engram Workflow** (if applicable) - Process for closing beads with learning:
   - Writing specific tests
   - Creating unit tests
   - Running tests to verify
   - Committing changes
   - Using `bd close` to trigger automatic learning

4. **Workflow for AI Agents** - Step-by-step process:
   - Check ready work
   - Claim task
   - Understand requirement
   - Write test (test-first)
   - Implement
   - Verify tests pass
   - Document changes
   - Commit with tests mentioned
   - Close only when 100% complete

5. **Landing the Plane** - Session-ending checklist:
   - Review in-progress beads (only close if complete)
   - File remaining work
   - Ensure quality gates pass
   - Commit everything
   - Sync issue tracker
   - Clean git state
   - Verify clean state

6. **Issue Tracking with bd** - Guide for using beads:
   - Why bd (dependency-aware, git-friendly, agent-optimized)
   - Quick start commands
   - Issue types (bug, feature, task, epic, chore)
   - Priorities (0-4)
   - Best practices
   - Managing AI-generated planning docs in history/

7. **Agent Best Practices** - General guidelines:
   - Never start development servers
   - Verify work with tests
   - Keep commits focused and small
   - Write clear commit messages
   - Conservative approach when unsure about closure

## Usage

### Option 1: Load the skill manually

Load this skill in your session:

```bash
# The skill is at: .agents/skills/agentmd_init/SKILL.md
# This will inject the workflow guidance into your context
```

### Option 2: Use as a prompt command

When starting a new project, ask to "use the agentmd_init skill" to create/update AGENTS.md with all standard sections.

## What Happens

1. **If AGENTS.md doesn't exist**: Creates it with a project header and all standard sections
2. **If AGENTS.md exists**: Preserves all existing content and adds/updates only missing sections
3. **Maintains formatting**: Keeps consistent Markdown style with existing content
4. **Protects custom content**: Never removes or alters existing sections

## Key Principles

- **Testing is mandatory**: Every commit must have specific tests validating the functionality
- **Bead closure is conservative**: Only close when work is 100% complete and tests prove it
- **Real implementations**: Tests use actual code, not mocks (unless explicitly required)
- **Clean root directory**: All guidance goes in AGENTS.md or docs/, never status/planning files in root
- **Learning systems depend on quality**: Incomplete work creates bad learning signals

## Benefits

- ✅ Consistent agent workflow across projects
- ✅ Clear testing and closure criteria prevent incomplete work
- ✅ Structured session-ending procedures reduce state pollution
- ✅ Integration with bd (beads) for dependency-aware issue tracking
- ✅ Learning loop support (Engram/ACE framework compatible)
- ✅ Clean repository root (planning docs in history/)

## See Also

- AGENTS.md - The generated workflow guidance document
- docs/DEVELOPMENT.md - Detailed development workflows
- docs/EXPERIMENT_MANAGEMENT.md - Experiment naming and structure
- bd (beads) documentation - Issue tracking and workflow
