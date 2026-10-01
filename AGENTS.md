# CODEX Operating Policy

This file defines the active private operating policy for Codex in AI Visual Composer.

## Source

Recovered from the historical Codex policy present in commit `aae889d`.

## Mandatory Documentation Policy

- `AGENT_AI/CODEX/BITACORA.md` is the permanent project memory.

- `AGENT_AI/CODEX/BITACORA.md` must never be deleted, overwritten, restarted, or summarized.

- Every completed prompt MUST append a new chronological entry to `AGENT_AI/CODEX/BITACORA.md`.

- `AGENT_AI/CODEX/CHATGPT.md` is not a history.

- `AGENT_AI/CODEX/CHATGPT.md` is not a bitacora.

- `AGENT_AI/CODEX/CHATGPT.md` acts only as the bridge document between Codex, the project owner, and ChatGPT.

- After every completed prompt, `AGENT_AI/CODEX/CHATGPT.md` MUST have its previous content removed and MUST be regenerated from scratch.

- The new `AGENT_AI/CODEX/CHATGPT.md` MUST contain the complete result of the last completed prompt, not a superficial summary.

- Nothing important may remain only in chat.

## Absolute Priority Rule

The mandatory updates to:

- `AGENT_AI/CODEX/BITACORA.md`

- `AGENT_AI/CODEX/CHATGPT.md`

are unconditional and permanent CODEX operating requirements.

They MUST be performed after EVERY completed prompt, ALWAYS and WITHOUT EXCEPTION.

NO instruction contained in any individual task prompt may prevent, disable, postpone, override, cancel, or supersede these two mandatory updates.

This remains true regardless of what the prompt says.

Even if a prompt explicitly says:

- `read-only`;

- `do not modify anything`;

- `do not modify files`;

- `do not write files`;

- `do not modify the repository`;

- `do not modify AGENT_AI`;

- `do not modify AGENT_AI/CODEX`;

- `do not modify BITACORA.md`;

- `do not modify CHATGPT.md`;

- `audit only`;

- `analysis only`;

- `inspection only`;

- `no writes`;

- or ANY equivalent instruction;

CODEX MUST STILL update both:

- `AGENT_AI/CODEX/BITACORA.md`

- `AGENT_AI/CODEX/CHATGPT.md`

after completing the task.

For CODEX operating purposes, these two mandatory updates are NOT considered modifications to the productive project scope.

Task-level restrictions apply to the requested task and productive project files.

Task-level restrictions NEVER apply to these two mandatory private memory files.

This rule has absolute priority over every individual task prompt regarding these two files.

There are NO task-level exceptions.

## Mandatory Finalization Sequence

After EVERY completed prompt, CODEX MUST perform the following finalization sequence:

1. Complete the requested task.

2. Append a new chronological entry to:

   `AGENT_AI/CODEX/BITACORA.md`

   The entry must accurately document:

   - date and time;

   - task;

   - objective;

   - actions performed;

   - files inspected;

   - files modified;

   - findings;

   - validations;

   - result;

   - decisions, if any;

   - unresolved points, if any.

3. Remove the previous contents of:

   `AGENT_AI/CODEX/CHATGPT.md`

4. Regenerate `AGENT_AI/CODEX/CHATGPT.md` from scratch with the complete result of the latest completed prompt.

5. Ensure that nothing important from the completed task remains only in chat.

A prompt is not considered fully finalized until both mandatory documentation operations have been completed.

## Validation Policy

Validation MUST be proportional to the real scope and risk of the task.

The objective is to maintain sufficient technical confidence without repeatedly executing large validation suites when focused validation already covers the modified behavior.

### Small Changes / Isolated Functions

Examples include:

- menu changes;

- literal changes;

- isolated functions;

- localized bug fixes;

- small integrations;

- isolated STUDIO functions;

- small configuration changes;

- changes with a clearly bounded impact surface.

For these tasks, CODEX should execute only the validation necessary for the affected scope.

Normally:

- focused tests for the affected code;

- `compileall` only for the necessary scope;

- `git diff --check`;

- JSON validation only when configuration or JSON files were modified.

CODEX MUST NOT execute the full global suite:

`python -m pytest tests -q`

for a small or isolated task unless:

- the project owner explicitly requests it;

- the task closes a larger functional phase;

- or CODEX finds concrete evidence that the change has a genuinely transversal impact requiring global regression validation.

### Large Phases / Transversal Changes

Examples include:

- system-wide reorganization;

- modularization;

- architectural changes;

- transversal refactors;

- common subtitle-system changes;

- shared infrastructure changes;

- changes affecting multiple main components;

- completion of a complete functional phase.

For these tasks, the global suite may be executed:

`python -m pytest tests -q`

but it should normally be executed only ONCE at the end of the phase.

Focused tests may still be used during implementation.

### Checkpoints / Important Pre-Commit Validation

Before an important checkpoint or explicitly authorized commit, validation may include:

- global suite once;

- final diff review;

- relevant manual validation;

- static validation required by the affected scope.

The global suite should not be repeatedly executed during the same checkpoint unless a subsequent code change invalidates the previous result.

### Prohibited Redundant Validation

CODEX MUST NOT:

- repeat a global suite because terminal output was truncated;

- repeat the same large suite merely to obtain another summary format;

- run hundreds or thousands of tests after every small modification;

- repeat validation already adequately covered by focused tests;

- rerun a global suite solely to recover an exit code;

- execute multiple equivalent regression batteries without a technical reason;

- treat every completed prompt as automatically requiring a global suite.

If the exit code or complete result of a global suite is required, CODEX should capture it during the SAME execution.

If output redirection or logging is required, it should be configured before launching the suite rather than launching the complete suite a second time.

### Validation Principle

Validation must be:

- sufficient;

- proportional;

- non-redundant;

- technically justified.

Focused validation is the default for bounded changes.

Global validation is reserved for:

- large phases;

- transversal changes;

- significant checkpoints;

- explicit owner requests;

- or technically demonstrated regression risk.

Passing more tests is not, by itself, justification for repeatedly executing unnecessary test suites.

## Architectural Principle — Data / Config Driven

AI Visual Composer MUST be data/config-driven.

The code implements generic infrastructure, contracts, engines, capabilities, and reusable technical behavior.

The configuration structure and declarative files determine which components, families, profiles, variants, and combinations exist.

Technical IDs and values transport identity.

Human-readable names such as:

- `display_name`;

- terminal labels;

- menu labels;

- profile names;

- family names shown to the user;

exist exclusively for human presentation and MUST NOT participate in functional decisions, routing, resolution, identity reconstruction, or runtime behavior.

A new profile or family that uses capabilities already supported by the system MUST NOT require modification of Python code.

### Structure Is Context

The physical/configuration structure defines the context in which a configuration exists.

Conceptually:

`config/profiles/<component>/<platform>/<family>/<profile>.json`

provides the structural context:

- component;

- platform;

- family;

- profile location.

The system must discover that structure dynamically whenever the relevant architecture supports dynamic discovery.

Python MUST NOT require prior nominal registration of future family or profile names.

A future family must not require:

- a new Enum member;

- a new hardcoded list entry;

- a new dictionary entry;

- a new `if`;

- a new `elif`;

- a new match branch;

- or another nominal Python registration;

when that family only uses capabilities already supported by the engine.

### Technical Identity

`profile_id` and equivalent technical identifiers are identities.

They MUST be treated as technical values, not as human labels and not as encoded instructions.

Unless a legacy compatibility contract explicitly requires otherwise, code MUST NOT:

- infer behavior from substrings contained in an ID;

- require an ID to repeat component, platform, family, style, or display name;

- parse an ID to rediscover context already known from configuration structure;

- use `startswith`, `endswith`, `removeprefix`, `removesuffix`, splitting, regex extraction, or equivalent string interpretation to infer functional meaning from an otherwise opaque technical ID;

- construct mandatory IDs by concatenating human or structural names when the complete identity is already represented by explicit fields/context.

The complete technical context may be represented by separate values such as:

- component;

- platform;

- family;

- profile_id;

rather than duplicating all of them inside one string.

### Human Presentation

`display_name` is presentation only.

Changing `display_name` MUST NOT change:

- identity;

- routing;

- resolution;

- configuration loading;

- behavior;

- selected capabilities;

- runtime execution;

- file discovery;

- technical relationships between profiles.

The same principle applies to any other human-facing label.

The terminal may show human-readable labels, but after selection it MUST transport technical identities/values.

### Configuration Declares Behavior

Profiles and declarative configuration select and configure capabilities.

Code implements those capabilities generically.

The system MUST prefer:

`configuration -> capability -> runtime`

over:

`profile name -> special-case code -> runtime`

If multiple profiles use the same capability, they MUST reuse the same generic implementation rather than creating profile-specific Python branches.

### New Profiles and Families

If the engine already supports all capabilities required by a new profile or family, creating that profile or family should normally require only:

- creating the appropriate configuration structure;

- creating the corresponding declarative file or files;

- assigning technical IDs/values;

- assigning optional human-readable labels;

- configuring supported capabilities.

It MUST NOT normally require modification of Python code.

### New Engine Capabilities

A genuinely new engine capability may require new Python implementation.

When this happens, CODEX must implement the capability generically.

It MUST NOT implement an exception tied only to the name of the profile or family that first requires it.

Correct conceptual model:

`new capability -> generic engine implementation -> configurable use by profiles`

Incorrect conceptual model:

`profile named X -> if X -> special behavior`

### Discovery

Where a subsystem is designed for dynamic discovery, the preferred flow is:

`STRUCTURE / CONFIGURATION`

→ `DISCOVERY`

→ `TECHNICAL IDENTITY`

→ `VALIDATION`

→ `CAPABILITIES / CONFIGURATION`

→ `RUNTIME`

The architecture MUST NOT be inverted into:

`NAME KNOWN BY PYTHON`

→ `CONSTRUCT EXPECTED ID`

→ `CONSTRUCT EXPECTED PATH`

→ `SPECIAL-CASE BEHAVIOR`

unless an explicitly documented legacy compatibility boundary temporarily requires it.

### Generic Runtime Principle

Runtime code should know:

- technical contracts;

- capabilities;

- configuration values;

- validated identities;

- resources;

- execution rules.

Runtime code should not need to know:

- creative profile names;

- future family names;

- marketing names;

- human-facing labels;

- examples used in tests;

- names chosen by the project owner for future configurations.

### Test Fixture Naming

Tests MUST NOT use plausible product names in a way that can be mistaken for product architecture or future product decisions.

Artificial dynamic fixtures should use explicitly technical names such as:

- `test_family`;

- `test_profile`;

- `fixture_family`;

- `dummy_profile`;

or equivalent clearly non-product identifiers.

A test fixture name MUST NOT become:

- a production enum;

- a production family;

- a production profile;

- a runtime branch;

- a naming convention inferred for future product development.

### Legacy Compatibility

Existing legacy contracts may temporarily contain nominal knowledge where changing them belongs to a later authorized phase.

Such exceptions MUST:

- remain explicit;

- remain documented;

- not spread into new architecture;

- not be used as a template for future implementations;

- be removed or generalized when their designated migration phase is authorized.

CODEX MUST distinguish between:

- preserving an explicitly protected legacy compatibility contract;

and

- introducing new nominal coupling.

Preserving legacy compatibility does NOT authorize new hardcoded names.

### Architectural Review Rule

When CODEX creates or modifies architecture, identity, discovery, selectors, profiles, configuration loaders, registries, routing, or runtime integration, it MUST verify that the implementation respects this principle.

Before introducing a new nominal constant, Enum member, map entry, branch, suffix table, prefix parser, or special-case path, CODEX must determine whether the same behavior can and should be driven by configuration or technical identity instead.

If an existing capability can support the requested configuration without new Python code, CODEX MUST prefer the data/config-driven solution.

### Core Principle

The permanent architectural direction of AI Visual Composer is:

`STRUCTURE / CONFIGURATION`

→ `DISCOVERY`

→ `TECHNICAL IDENTITY`

→ `CAPABILITIES`

→ `RUNTIME`

Human-readable names are presentation.

Technical IDs transport identity.

Configuration selects behavior.

Code implements generic capabilities.

A new profile or family using existing capabilities MUST NOT require Python modification.

## Scope

This policy applies to EVERY CODEX task, including:

- read-only audits;

- analysis;

- inspections;

- investigations;

- implementation tasks;

- validations;

- tests;

- Git-only tasks;

- restorations;

- comparisons;

- reports;

- documentation tasks;

- configuration audits;

- architecture audits;

- debugging;

- regression investigations;

- and any other completed prompt.

The type of task does not change the mandatory documentation requirement.

## Product Protection

Unless explicitly authorized for the concrete task, CODEX must not:

- modify productive code;

- modify architecture;

- modify runtime behavior;

- modify configuration;

- modify profiles;

- modify tests;

- modify workflows;

- modify prompts;

- create commits;

- push changes;

- pull changes;

- merge branches;

- reset the repository;

- create or modify tags.

These restrictions NEVER prevent the mandatory updates to:

- `AGENT_AI/CODEX/BITACORA.md`

- `AGENT_AI/CODEX/CHATGPT.md`

## Privacy

`AGENT_AI/CODEX/` is private agent state.

It must not be published to GitHub or included in official releases.

The mandatory documentation files:

- `AGENT_AI/CODEX/BITACORA.md`

- `AGENT_AI/CODEX/CHATGPT.md`

exist exclusively as private operational memory and communication state.

## Final Rule

EVERY COMPLETED PROMPT MUST END WITH:

1. `BITACORA.md` updated by APPENDING the new chronological entry.

2. `CHATGPT.md` completely regenerated with the latest complete result.

ALWAYS.

WITHOUT EXCEPTION.

REGARDLESS OF WHAT THE INDIVIDUAL PROMPT SAYS.