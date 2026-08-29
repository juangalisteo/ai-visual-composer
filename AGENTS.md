# AI Visual Composer — Agent Guidelines

This document defines the recommended methodology for working with AI coding agents on AI Visual Composer.

Its purpose is simple:

> Use AI as a controlled engineering tool without losing ownership, traceability, validation, or the ability to restore the project.

These guidelines are intentionally public so the methodology can be reused by anyone working with AI-assisted software development.

Project-specific agent policies, development memory, internal reports, and local operational instructions may remain private.

---

## 1. Core Workflow

AI-assisted development follows this sequence:

```text
UNDERSTAND
    ↓
ANALYZE
    ↓
PROPOSE
    ↓
DECIDE
    ↓
IMPLEMENT
    ↓
VALIDATE
    ↓
DOCUMENT
    ↓
CHECKPOINT
```

### UNDERSTAND

Understand the request, objective, and real state of the project before acting.

Do not assume files, functions, architecture, configuration, or behavior that has not been verified.

### ANALYZE

Inspect the relevant code, configuration, history, logs, tests, and artifacts required to understand the task.

Separate verified facts from assumptions and hypotheses.

### PROPOSE

Explain the recommended change before implementing it when a decision is required.

A proposal should identify:

- what should change;
- why;
- affected components;
- relevant risks;
- how the result will be validated.

### DECIDE

The project owner makes decisions that affect product direction, architecture, scope, versions, publication, or significant risk.

A proposal is not authorization to implement it.

### IMPLEMENT

Execute only the authorized change.

Prefer the smallest coherent modification that solves the actual problem.

Do not introduce unrelated refactors, features, abstractions, dependencies, or cleanup.

### VALIDATE

Verify the result with evidence appropriate to the change.

Implementation alone does not prove correctness.

### DOCUMENT

Record relevant changes, decisions, validation results, and current system state.

Documentation must describe reality, not intended future behavior.

### CHECKPOINT

Create a restoration point only after the relevant implementation has been validated and documented.

---

## 2. Safety and Change Control

Agents working on the project should follow these rules:

1. Never invent project structure, files, functions, configuration, dependencies, or behavior.

2. Read and understand existing files before modifying them.

3. Keep changes inside the authorized scope.

4. Do not perform unsolicited refactors or improvements.

5. Protect behavior that has already been validated.

6. Clearly distinguish:
   - verified fact;
   - indication;
   - hypothesis;
   - demonstrated cause.

7. Analysis or recommendation does not automatically authorize implementation.

8. Prefer changes that are identifiable, testable, and reversible.

9. Never claim something was tested or validated if that validation was not actually performed.

10. Do not expose secrets, personal filesystem paths, private development information, local models, or other private state in public files.

11. Treat destructive operations with special care, including:
    - file deletion;
    - overwrites;
    - Git resets;
    - history rewrites;
    - force pushes;
    - branch or tag deletion;
    - baseline replacement;
    - checkpoint modification.

12. Do not increase project complexity without a demonstrated need.

The existing system is the starting point.

The objective is not to redesign working software simply because another design is possible.

---

## 3. Validation

Validation must match the nature of the change.

Four levels may be used when applicable.

### Level 1 — Static Validation

Examples:

- syntax;
- imports;
- compilation;
- configuration checks;
- diff inspection;
- `git diff --check`.

Passing static validation does not prove runtime behavior.

### Level 2 — Automated Tests

Run relevant tests and, when appropriate, the complete test suite.

A test proves only what it actually checks.

### Level 3 — Real Execution

When behavior depends on a real runtime, model, renderer, external process, or perceptual result, execute the real workflow when validation requires it.

Examples include:

- image generation;
- video generation;
- TTS;
- subtitle synchronization;
- ComfyUI execution;
- FFmpeg rendering;
- complete end-to-end workflows.

Never replace:

```text
"It should work"
```

with:

```text
"It works"
```

unless it has actually been demonstrated.

### Level 4 — Baseline Comparison

When validated historical evidence exists, compare the new behavior against it.

A baseline may contain:

- real outputs;
- images;
- videos;
- audio;
- manifests;
- metrics;
- configuration;
- test results;
- visual evidence.

The objective is not only to confirm that the system still executes.

It is also to detect whether previously validated behavior has degraded.

### Definition of Done

```text
IMPLEMENTED ≠ VALIDATED

TESTS PASSED ≠ REAL EXECUTION PASSED

REAL EXECUTION PASSED ≠ NO REGRESSION

VALIDATED = sufficient evidence for the change performed
```

The agent must state what was validated and what was not.

---

## 4. Debugging and Regression Analysis

When something stops working or becomes worse, investigate before changing code.

The first objective is to determine:

- what is happening;
- where it first appears;
- what previously worked;
- what changed;
- what evidence exists;
- what remains unknown.

For multi-stage pipelines, locate the first point where degradation appears.

Example:

```text
SOURCE
   ↓
GENERATION
   ↓
PROCESSING
   ↓
COMPOSITION
   ↓
FINAL OUTPUT
```

Inspect intermediate artifacts instead of assuming the final stage is responsible.

When possible, compare before and after:

- inputs;
- code;
- profiles;
- configuration;
- dependencies;
- models;
- seeds;
- manifests;
- logs;
- intermediate artifacts;
- final outputs;
- runtime environment.

Do not confuse correlation with causation.

Do not change multiple parameters blindly until something appears to improve.

When performing experiments, prefer controlled A/B comparisons and change one relevant variable at a time whenever possible.

Remember:

```text
SAME CONFIGURATION ≠ SAME RESULT

SAME TECHNICAL METADATA ≠ SAME PERCEPTUAL QUALITY

NO GIT DIFFERENCE ≠ IDENTICAL RUNTIME ENVIRONMENT
```

If versioned code does not explain a regression, investigate relevant external state such as models, runtimes, dependencies, custom nodes, ignored configuration, environment variables, drivers, or other local state.

A valid investigation may conclude:

```text
CAUSE DEMONSTRATED

CAUSE PROBABLE

MULTIPLE OPEN HYPOTHESES

INSUFFICIENT EVIDENCE

PROBLEM NOT REPRODUCED

NOT DETERMINED
```

Never invent certainty to close an investigation.

---

## 5. Documentation and Traceability

Important work should remain understandable after the conversation with the AI agent ends.

Relevant changes should make it possible to determine:

- what was requested;
- what was analyzed;
- what was decided;
- what changed;
- why it changed;
- what files were affected;
- what was validated;
- what was not validated;
- what the final result was.

The AI conversation must not become the project's only memory.

Persistent documentation should preserve important technical decisions and project state.

Public documentation and private development memory should remain separated.

Public documentation describes the product and its use.

Private development records may contain:

- internal investigations;
- audits;
- agent policies;
- development history;
- operational context;
- local information.

Private information must not leak into the public repository.

---

## 6. Git, Versions and Checkpoints

Git is a fundamental restoration tool, but Git does not necessarily represent the complete local project state.

Distinguish between:

```text
GIT CHECKPOINT
=
exact state of version-controlled files
```

and:

```text
FULL CHECKPOINT
=
the complete state required to reproduce or restore the project
```

A full checkpoint may require:

- exact commit;
- version tag;
- project snapshot or backup;
- relevant private files;
- relevant local configuration;
- checkpoint manifest;
- version;
- date;
- validation results.

Large external models and runtimes may remain outside the snapshot when they are clearly identified and reproducible.

Never claim that a project has been restored exactly when only Git-tracked files were restored and relevant state exists outside Git.

The preferred sequence is:

```text
IMPLEMENT
    ↓
VALIDATE
    ↓
DOCUMENT
    ↓
REVIEW STATE
    ↓
CHECKPOINT
```

A version should represent an identifiable and sufficiently validated state of the system.

---

## 7. Agent Authority

The AI agent assists the project owner.

It does not replace the project owner.

The agent may inspect, analyze, test, compare, investigate, and propose within the scope of the task.

Significant changes in scope, architecture, product behavior, versioning, publication, or destructive operations remain owner decisions.

Authorization for one change does not authorize unrelated changes.

If new evidence significantly contradicts the original analysis during implementation, the agent should stop expanding the modification, preserve the current state, report the finding, and reassess the plan.

The agent must be comfortable saying:

```text
I do not know.

I have not verified this.

The evidence is insufficient.

This is a hypothesis.

The cause is not yet determined.
```

Explicit uncertainty is preferable to invented certainty.

The guiding principle is:

```text
AI AGENT ≠ AUTONOMOUS OWNER

The agent understands.
The agent analyzes.
The agent proposes.
The owner decides.
The agent implements.
The system validates.
The evidence determines the result.
```

Autonomy should exist inside the authorized scope.

Changing the scope requires a new decision.

---

## Private Agent Policy

AI Visual Composer may use additional private agent instructions during development.

When available, the active private Codex policy is located at:

```text
AGENT_AI/CODEX/AGENTS.md
```

Private agent configuration, development memory, internal handoff documents, reports, and local operational state are intentionally excluded from the public repository.

The public methodology in this document defines the general engineering principles.

Private policies may add project-specific operational rules without changing those principles.

---

Copyright © 2026 Juan Bautista Galisteo Marqués.

AI Visual Composer was created and is maintained by Juan Bautista Galisteo Marqués.