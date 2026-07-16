# Changelog

All notable changes to AI Video Composer will be documented in this file.

This project follows a conventional Open Source changelog structure. Dates are intentionally omitted until release tagging is formalized.

## [Unreleased]

### Added

- First functional Visual Director subsystem for backend-neutral image prompt enrichment.
- Directed prompt metadata in the image manifest, including positive prompt, negative prompt, fallback state, and visual directives.
- Characterization tests for Visual Director and its ImageBuilder integration.
- Global Safe Visual Policy for image generation prompts.
- Safe visual policy metadata in the image manifest.

### Changed

- ImageBuilder now enriches scene prompts through Visual Director before image backend prompt injection, while preserving the legacy prompt as fallback.
- ImageBuilder now applies safe-for-work prompt enforcement before every image backend request.

## [1.0.0] - Motor Core Completed

### Summary

- Core engine completed.
- Architecture stabilized.
- Pipeline stabilized.
- Final audit completed.

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

### Validated

- Unit test suite.
- Python compilation.
- Real horizontal renders.
- Real vertical renders.
- Overlay renders.
- Visual effect renders.
- Combined overlay and visual effect renders.
- Transition-specific renders.
- FFmpeg metadata probing.
- Visual frame inspection.
