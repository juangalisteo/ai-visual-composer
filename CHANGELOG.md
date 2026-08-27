# Changelog

All notable changes to AI Visual Composer will be documented in this file.

## [Unreleased]

No unreleased changes.

## [V2.0] - 2026-08-25

### Added

- Documented and validated the three current product entries: Guion, Imagen, and Video.
- Added V2.0 validation baselines for Guion, Imagen, and Video under `validation/v2_0/`.
- Added complete baseline artifacts for each component: reports, JSON metrics, CSV metrics, inventories, samples manifests, samples, and charts.
- Added validated Video product routing with complete mode, partial audio/subtitle/storyboard modes, I2V clip generation, video clip manifests, and final FFmpeg composition.
- Added validated design-to-image and design-to-video routes through dedicated manual inputs.
- Added validated ping-pong I2V loop composition using existing clips without regenerating Wan output.
- Added validated Motion application over generated I2V clips in the FFmpeg composition graph.

### Changed

- Updated the public documentation to describe the real V2.0 system instead of the previous V.1 / PR1 baseline.
- Updated the documented console entry to the current product menu: Guion, Imagen, and Video.
- Updated baseline metadata so Imagen references the current `output/imagen/` location.
- Homogenized Video baseline metrics with the Guion and Imagen baseline schema for direct comparison.
- Moved ping-pong/reverse I2V looping and Motion over I2V clips into the V2.0 validated state after real render approval.

### Validated

- Guion baseline: 20 real executions.
- Imagen baseline: 8 real executions.
- Video baseline: 8 real executions.
- Total V2.0 baseline: 36 real executions.
- Full test suite at pre-checkpoint audit: 837 tests passing.
- Real render validation by the owner for ping-pong I2V looping and Motion over I2V clips.
- Python compilation over `app`, `tests`, and `certification`.
- Baseline JSON and CSV structure.
- `git diff --check`.

## [V.1] - 2026-08-13

### Changed

- Established AI Visual Composer `V.1` as the official stable general system version.
- Established `PR1` as the first official restoration point inside `V.1`.
- Normalized the public restoration structure so previous development PR tags no longer define the official restoration sequence.
- Reviewed and corrected public documentation before the V.1 stable closure.
- Updated `README.md` with the real startup sequence: `ollama serve`, `cd ComfyUI` + `.\run_nvidia_gpu.bat`, then `python main.py`.
- Documented the real Ollama model from `config/ai.json`: `qwen3:14b`.
- Updated documentation for current console modes, music selection, smart overlays, `Light Leaks` neutral fallback, weighted overlay category distribution, and per-video overlay category cooldown.
- Replaced the previous pre-Version-1.0 closure language with the official `V.1 / STABLE / PR1` baseline.
- Integrated post-PR1 development work into the V.1 stable baseline: PromptTranslator observability, evidence persistence, OVB-001 benchmark infrastructure, Visual Quality validation flow, and ImageBuilder evidence integration.
- Reorganized technical reports from the repository root into `docs/architecture/` and `docs/reports/image-pipeline/`, keeping the root focused on official product entry-point documents and utilities.
- Clarified that current Visual Quality product checks consume explicit validation signals and artifact integrity evidence; they do not independently perform OCR, logo recognition, face analysis, anatomy analysis, object detection, or pixel-level visual inference.
- Added the missing `edge_tts` runtime dependency declaration required by `app/modules/audio/voice_builder.py`.
- Regenerated `project_tree.txt` and updated `generate_project_tree.py` documentation so private local folders such as `CODEX/`, `ComfyUI/`, `output/`, `logs/`, `input/`, `.git/`, `.agents/`, and `backup_*` are omitted from the public architecture tree.
- Created `PR1` as the first Official Restoration Point for AI Visual Composer, establishing the stable reference state for future rollback, audits, optimizations, refactors, backend experiments, and architectural evolution.
- Added structured Script Generation output validation so conversational LLM responses cannot enter voice, subtitles, storyboard, Visual Intelligence, Prompt Translation, or image generation.
- Corrected Prompt Translation to compile compact backend-neutral prompts with deterministic backend/model budget policy, semantic compaction, traceability-preserving source fields, and useful ComfyUI error categories for prompt-length and memory failures.
- Published `Visual Intelligence Architecture v1.0` as the official frozen specification for the canonical Image Runtime architecture.
- Retired transitional Visual Direction and Runtime Cognitive compatibility components; the Image Runtime now proceeds from `StoryboardSceneAdapter` through Visual Analysis, Visual Reasoning, Visual Synthesis, `EffectiveVisualBrief`, cinematic direction, prompt translation, and backend adaptation.
- Certified the Visual Intelligence performance baseline with deterministic timing, memory, object, contract, and fingerprint measurements.
- Certified the Visual Intelligence runtime pipeline with end-to-end determinism, traceability, boundary, duplicate-contract, and inverse-adapter guards.
- Integrated Visual Intelligence into the image runtime so `ImageBuilder` now builds and propagates `VisualSynthesisResult` before cinematic direction, prompt translation, and backend adaptation.
- Classified `EffectiveVisualBrief` as `CANONICAL` and remaining compatibility fields/models as `TRANSITIONAL` before `IP3.0-5`.
- Audited legacy compatibility fields after canonical `EffectiveVisualBrief` unification; retained active compatibility fields with explicit temporary markers pending `IP3.0-5`.
- Consolidated `EffectiveVisualBrief` as a single canonical contract in `app/domain/visual_intelligence.py`; the temporary `app.visual_direction` compatibility reexport used during migration has since been retired.
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
- Foundation completed: public UTF-8 verification, official asset policy, and private AVCES policy.
- Certified final repository identity and documentation compliance with private AVCES v1.0 governance.
- Defined the private development environment policy.
- Updated public documentation to keep `CODEX/` outside the public repository and official releases.
- Extended `.gitignore` for private development memory, external runtimes, LoRAs, VAE files, embeddings, and ControlNet resources.

## [1.0.0] - Historical planning reference

### Summary

- Historical planning record for the first official AI Visual Composer baseline before the project adopted the `V.1` general-version and `PR1` restoration-point structure.
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
