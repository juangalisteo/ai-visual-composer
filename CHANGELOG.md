# Changelog

All notable changes to AI Visual Composer will be documented in this file.

## [Unreleased]

### Changed

- Implemented the IP3.0 Visual Synthesis Layer with conflict reporting, Effective Visual Brief synthesis, unified Visual Intelligence trace building, a Visual Synthesis orchestrator, and `VisualSynthesisResult` as the passive boundary contract before runtime integration.
- Implemented the IP3.0 Visual Reasoning Layer with Scene Intent, Visual Intelligence Strategy, Sequence Continuity, an isolated reasoning orchestrator, deterministic traces, and stable fingerprints without runtime, backend, prompt, workflow, or Visual Quality integration.
- Implemented the IP3.0 Visual Analysis Layer with Visual Truth inspection, visual semantics resolution, visual priority resolution, an isolated analysis orchestrator, deterministic traces, and stable fingerprints without runtime, backend, prompt, workflow, or Visual Quality integration.
- Added specialized Visual Intelligence contracts for inspection, semantics, priority, scene intent, strategy, sequence continuity, conflicts, and specialized traces without resolver or runtime integration.
- Added passive Visual Intelligence core contracts for IP3.0 without runtime, backend, prompt, or resolver integration.
- Retired the legacy storyboard contract by removing `subject`, `action`, `setting`, and `legacy_visual_idea` as operational Image Pipeline inputs.
- Removed `visual_idea` from generated storyboards and migrated real image certification fixtures to pure Visual Truth 2.0.
- Migrated runtime narrative reading to use Visual Truth 2.0 as its primary source while keeping legacy storyboard fields isolated as compatibility fallback.
- Extended `NarrativeEvent` with passive Visual Truth context fields for environment, time, objects, spatial relationships, continuity, constraints, status, and source model.
- Migrated storyboard generation to Visual Truth 2.0 as the primary visual source.
- Adopted the private AVCES v1.0 engineering standard for repository governance.
- Foundation completed: public UTF-8 verification, official asset policy, private AVCES policy, and planned RuntimeCognitiveAdapter 2.0 status.
- Certified final repository identity and documentation compliance with private AVCES v1.0 governance.
- Defined the private development environment policy.
- Updated public documentation to keep `CODEX/` outside the public repository and official releases.
- Extended `.gitignore` for private development memory, external runtimes, LoRAs, VAE files, embeddings, and ControlNet resources.

## [1.0.0] - AI Visual Composer v1.0.0

### Summary

- First official release candidate base for AI Visual Composer.
- Image Component 1.0 certified as `IMAGE_COMPONENT_1_0_READY`.
- AI Visual Composer product entry added.
- Image Pipeline established as the first official product pipeline.
- Video Pipeline exposed only as a future option.
- Final Project Cleanup completed.

### Added

- Single cinematic Image Component runtime.
- Runtime adapters for storyboard scenes, cognitive input, and generation results.
- Cinematic direction orchestration.
- Prompt Translator and `BackendPrompt`.
- ComfyUI backend adapter integration.
- Visual Quality contracts, gate, image validator, retry policy, and certification support.
- Image Component certification suite.
- Real certification campaign infrastructure.
- AI Visual Composer pipeline selector.
- Product documentation for external dependencies and runtime setup.

### Changed

- Project identity updated to AI Visual Composer.
- Repository target name updated to `ai-visual-composer`.
- ImageBuilder now coordinates the single certified Image Component runtime.
- Prompt construction now flows through backend-neutral contracts before ComfyUI execution.
- Documentation simplified to one official README and one active reference document.
- `.gitignore` now explicitly excludes local AI models, checkpoints, downloads, generated outputs, logs, local secrets, and external runtimes.

### Removed

- Legacy image runtime path.
- Legacy domain adapters.
- Legacy Visual Director runtime module.
- `VideoOverlayFilter` dead code.
- Obsolete Visual Director tests.
- Obsolete legacy adapter tests.
- Duplicated and temporary documentation.
- Temporary project structure document.
- Redundant frozen requirements file.
- Generated outputs and debug logs from the working tree.

### Preserved

- Public video render facade.
- Profile-driven video configuration.
- FFmpeg video composition core.
- Motion, Transitions, Overlays, Visual Effects, Fade, and Subtitles pipeline order.
- Image manifest compatibility with downstream video assembly.
- Existing profile system.
- Existing ComfyUI workflow configuration.

### Validated

- Unit test suite.
- Python compilation for `app`, `tests`, and `certification`.
- `git diff --check`.
- Image Component RC0 quick real smoke campaign.
- Product entry flow through `AI VISUAL COMPOSER -> Image Pipeline`.

## [0.1.0] - Motor Core Completed

### Summary

- Original video core completed.
- Architecture stabilized.
- Pipeline stabilized.
- Final core audit completed.

### Added

- Profile-driven video configuration.
- Modular video composition pipeline.
- Motion stage.
- Transition stage using FFmpeg `xfade`.
- Overlay stage.
- Visual Effects stage.
- Fade stage.
- Subtitle stage.
- FilterPipeline execution layer.
- CommandPlanBuilder.
- CommandBuilder.
- VideoBuilder public facade.
- Runner execution layer.
- VideoValidator output validation.
- Professional project documentation.

### Stabilized

- Visual Effects.
- Overlays.
- Motion.
- Transitions.
- CommandBuilder.
- VideoBuilder.
- FFmpeg input handling.
- `filter_complex` generation.
- Auxiliary input indexing.
- Horizontal render validation.
- Vertical render validation.
- Combined layer render validation.
