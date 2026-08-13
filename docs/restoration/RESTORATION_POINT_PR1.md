# Official Restoration Point

## Identifier

PR1

## General Version

V.1

## Date

2026-08-13

## Status

STABLE

## Description

This document represents the first official restoration point of AI Visual Composer V.1.

The current system state has been developed, tested, documented, and validated as stable before establishing this point.

If a future optimization, refactor, backend experiment, architecture change, or feature introduces a regression, the project may be restored to this point.

## Version And Restoration Structure

`V.1` identifies the general system version.

`PR1` identifies the first stable restoration point inside `V.1`.

Official structure:

```text
V.1
|
└── PR1 - STABLE
```

Future stable restoration points inside `V.1` may be named `PR2`, `PR3`, `PR4`, and so on.

`V.2` must only be created after an explicit owner decision.

## Frozen Architecture Reference

`project_tree.txt` represents the official architecture tree captured for `PR1`.

The tree is intentionally architectural. It excludes private development memory, local runtimes, generated outputs, logs, caches, local inputs, backups, and other resources that do not belong to the public product repository.

## Validated State

| Area | Status |
| --- | --- |
| Script Generation | VALIDATED |
| Script Output Contract | VALIDATED |
| Voice | VALIDATED |
| Subtitles | VALIDATED |
| Storyboard | VALIDATED |
| Visual Truth 2.0 | VALIDATED |
| Visual Intelligence | VALIDATED |
| Prompt Translation | VALIDATED |
| Image Runtime | VALIDATED |
| ComfyUI Integration | VALIDATED |
| FFmpeg Integration | VALIDATED |
| Video Composition Core | VALIDATED |
| Music Selection | VALIDATED |
| Smart Overlays | VALIDATED |
| Visual Effects | VALIDATED |
| Project Tree | VALIDATED |
| Public Documentation | VALIDATED |

## Included Product State

`PR1` captures the current product repository state, including:

- source code;
- configuration;
- tests;
- official public documentation;
- `project_tree.txt`;
- official assets;
- `assets/videos/overlays/`;
- current overlay folders and files;
- the stable console flow;
- the current image and video composition runtime.

## Excluded Private State

The following remain outside the public restoration point:

- `CODEX/`;
- `ComfyUI/`;
- `output/`;
- `logs/`;
- `input/`;
- `.env`;
- credentials;
- secrets;
- local AI models;
- caches;
- backups;
- renders;
- temporary files;
- private development resources excluded by project policy.

## Guarantees

This official restoration point guarantees that:

- the complete validated pipeline has a stable Git reference;
- the architecture can evolve from a known stable base;
- future changes can be compared against `PR1`;
- regressions can be isolated by restoring or diffing against `PR1`;
- the public repository has a coherent V.1 restoration structure.

## Restoration

To restore this point after publication:

```text
git checkout PR1
```

`PR1` is the official stable restoration reference for AI Visual Composer V.1.

## Git Reference

Git tag:

```text
PR1
```

The exact commit SHA is resolved by the annotated Git tag `PR1`.
