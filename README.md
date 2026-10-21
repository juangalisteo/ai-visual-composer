# AI Visual Composer

**AI Visual Composer is a modular artificial intelligence-assisted system for audiovisual production, developed on a data/config-driven architecture.**

**Version:** `3.0`  
**Architecture:** `Data/Config-Driven`

## Documentación

- [Instalación](docs/INSTALL.md)
- [Arranque y parada](docs/START.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Hoja de ruta](docs/ROADMAP.md)

AI Visual Composer is a modular artificial intelligence-assisted system for audiovisual production, developed on a data/config-driven architecture. Artificial intelligence is an essential part of its operation and participates in the different stages of generation, interpretation, and processing that make it possible to turn scripts, ideas, and topics into complete audiovisual projects. This architecture establishes a clear separation between the technical capabilities implemented by the system and the entities defined through configuration, promoting extensibility, reuse, and the structured evolution of the system as a whole.

Conceived as an integrated production system, AI Visual Composer brings together within a single configurable environment the processes required to create, adapt, process, and finalize audiovisual content. Its architecture makes it possible to centralize tasks that would normally require separate tools and workflows, incorporating artificial intelligence-based generation, audiovisual processing, subtitling, translation, composition, and content adaptation. The system is particularly oriented toward the automation of production workflows for social media, with the goal of reducing manual intervention, reusing capabilities across different formats and platforms, and keeping the entire audiovisual production process within a unified operational structure.

---

## Architecture

AI Visual Composer follows a **data/config-driven architecture** based on a strict separation between technical implementation and configurable entities.

The architecture follows this principle:

```text
CODE
│
├── Generic technical capabilities
├── Fixed application components
├── Algorithms
├── Parsers
├── Loaders
├── Engines
├── Runtime services
└── Technical contracts

CONFIGURATION
│
├── Platforms
├── Families
├── Profiles
├── Variants
└── Values
```

### Code Responsibilities

Python implements the technical capabilities required by the system.

These capabilities contain the reusable logic needed for content processing, artificial intelligence integration, voice generation, subtitle processing, visual generation, audiovisual composition, configuration loading, routing, validation, and runtime execution.

Python also implements the fixed application components that define the main structural areas of AI Visual Composer:

```text
GUION
IMAGEN
VIDEO
STUDIO
TRADUCTOR
```

A component is therefore a structural capability of the application, not a configurable label. Introducing a genuinely new component or a new technical capability requires implementation because the system must first acquire that behavior.

### Configuration Responsibilities

Configuration determines how existing technical capabilities are organized, selected, combined, and adapted to different production contexts.

Depending on the configuration domain, the structure can define:

```text
platform
   ↓
family
   ↓
profile_id
   ↓
variants
   ↓
values
```

This allows the system to reuse the same technical capabilities across different platforms, families, profiles, formats, orientations, resolutions, subtitle configurations, and production requirements without duplicating the underlying Python implementation.

Not every configuration domain must use every level of this hierarchy. Each domain uses only the levels that belong to its own technical contract.

### Fixed Components and Configurable Entities

AI Visual Composer distinguishes clearly between **application structure** and **configuration structure**.

The application structure defines the fixed components:

```text
GUION
IMAGEN
VIDEO
STUDIO
TRADUCTOR
```

The configuration structure defines the entities and values that can vary without redefining the application itself.

This distinction prevents configurable entities from becoming hardcoded catalogs inside Python and keeps the system extensible without sacrificing architectural control.

### Technical Identity

Functional identity is transported through technical IDs.

Technical IDs are used to identify components, platforms, profiles, families, voices, subtitle profiles, and other configurable entities wherever identity must be preserved across the runtime.

Human-readable names do not define system behavior.

```text
TECHNICAL ID
     ↓
FUNCTIONAL IDENTITY

display_name / label
     ↓
PRESENTATION ONLY
```

Fields such as `display_name` and other visible labels exist exclusively to present understandable names to the user. They must not participate in functional decisions, routing, backend selection, or profile resolution.

### Discovery and Resolution

Configurable entities are discovered and resolved from configuration instead of being duplicated as nominal catalogs in Python.

The system reads the available configuration, transports its technical identity, and applies the capabilities already implemented by the code.

This means that configuration determines **which configured entity is used and with which values**, while Python determines **what the system is technically capable of doing**.

### Extensibility

The central extensibility rule is:

> A new platform, family, profile, variant, or value that uses capabilities already supported by AI Visual Composer must not require changes to Python code.

Configuration should be sufficient whenever the requested behavior can already be expressed through existing technical capabilities.

Python changes are justified when a genuinely new technical capability, algorithm, execution contract, backend integration, or application component must be introduced.

This keeps the system extensible without turning configuration into executable architecture or Python into a catalog of configurable names.

### Operational Profiles and Subtitle Profiles

Operational profiles and subtitle profiles are separate configuration domains.

Operational profiles identify the production behavior of a component for a specific platform and profile:

```text
OperationalProfileKey
(component, platform, profile_id)
```

Subtitle profiles identify subtitle behavior and additionally include their family:

```text
SubtitleProfileKey
(component, platform, family, profile_id)
```

The subtitle family therefore belongs to subtitle profile identity and does not redefine the identity of the operational profile.

This separation allows audiovisual production behavior and subtitle presentation behavior to evolve independently while remaining connected through explicit technical identities.

### Architectural Summary

The complete data/config-driven model can be summarized as:

```text
APPLICATION
│
├── GUION
├── IMAGEN
├── VIDEO
├── STUDIO
└── TRADUCTOR
        │
        ↓
GENERIC TECHNICAL CAPABILITIES
        │
        ↓
CONFIGURATION
├── Platforms
├── Families
├── Profiles
├── Variants
└── Values
        │
        ↓
TECHNICAL IDS
        │
        ↓
RUNTIME EXECUTION
        │
        ↓
AUDIOVISUAL OUTPUT
```

The architecture therefore preserves a clear rule:

```text
CODE DEFINES CAPABILITIES
CONFIGURATION DEFINES ENTITIES AND VALUES
TECHNICAL IDS DEFINE IDENTITY
HUMAN-READABLE NAMES DEFINE PRESENTATION
```

For a deeper description of the internal architecture, see **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Components

### GUION

**GUION** is the script-centered component.

It works from complete written content supplied by the user and preserves that source as the basis of the audiovisual workflow.

Its purpose is to prepare existing textual content and process it through the production capabilities required by the selected output.

### IMAGEN

**IMAGEN** is the image-centered production component.

It can develop a topic, idea, description, or brief text into a structured audiovisual project based on image generation.

Its workflow can combine content preparation, voice, audio, subtitles, storyboard construction, visual interpretation, image generation, manifests, and final audiovisual composition.

### VIDEO

**VIDEO** is the video-centered production component.

It extends the visual pipeline with Image-to-Video generation and temporal processing, allowing generated imagery to become audiovisual sequences before final composition.

Its workflow can combine image generation, I2V generation, motion, transitions, overlays, visual effects, subtitles, audio, and final video composition.

### STUDIO

**STUDIO** is the component dedicated to externally supplied audiovisual material.

It provides production and finishing workflows for video, audio, subtitles, montage, intro/outro composition, transcription, subtitle conversion, and final media preparation.

Its current operating modes are:

```text
SOLO VIDEO
SRT + VIDEO
INTRO / OUTRO
MONTAJE VÍDEOS
VIDEO + AUDIO SRT
EXPORTAR SRT VIDEO
```

### TRADUCTOR

**TRADUCTOR** is the multilingual translation and content-adaptation component of AI Visual Composer.

Its purpose is to integrate translation into the same audiovisual production environment so that content can be adapted for different languages, audiences, formats, and social-media destinations while preserving the architecture and reusable capabilities of the system.

---

## Main Capabilities

AI Visual Composer brings together the main capabilities required for an integrated audiovisual production workflow:

- script and topic-based content processing;
- artificial intelligence-assisted content generation and interpretation;
- local language-model processing;
- voice generation;
- audio preparation and mixing;
- transcription;
- subtitle generation and processing;
- configurable subtitle profiles;
- storyboard generation;
- structured visual interpretation;
- cinematic direction;
- prompt translation;
- AI image generation;
- Image-to-Video generation;
- motion and temporal preparation;
- transitions;
- overlays;
- visual effects;
- audiovisual composition;
- external-media processing through STUDIO;
- multilingual translation and content adaptation through TRADUCTOR;
- platform-oriented profiles and configuration;
- reusable production capabilities across different formats and destinations.

---

## Technologies

AI Visual Composer uses a local technical ecosystem built around:

- **Python** — application logic and orchestration;
- **Ollama** — local language-model execution;
- **ComfyUI** — local visual generation runtime;
- **Flux** — image generation;
- **Wan** — Image-to-Video generation;
- **Piper ONNX** — local text-to-speech;
- **OpenAI Whisper** — transcription and subtitle timing;
- **FFmpeg / FFprobe** — audiovisual processing, inspection, and final composition.

The system is designed so that these technical capabilities remain separated from the configurable entities that determine how they are used.

---

## Audiovisual Production for Social Media

AI Visual Composer is especially oriented toward the automation of audiovisual production workflows for social media.

The objective is to centralize within the same system tasks that would normally require multiple independent tools, reduce repetitive manual intervention, and reuse the same technical capabilities across different platforms, formats, profiles, and production requirements.

The data/config-driven architecture allows production behavior to be adapted through configuration while preserving a common technical foundation.

This makes it possible to evolve the system toward increasingly complete workflows for content creation, adaptation, translation, processing, and finalization without fragmenting the production environment.

---

## Installation

Initial installation and environment preparation are documented in:

**[INSTALL.md](docs/INSTALL.md)**

---

## Startup

Normal startup and shutdown procedures are documented in:

**[START.md](docs/START.md)**

---

## License

AI Visual Composer is released under the **MIT License**.

See **[LICENSE](LICENSE)** for the complete license terms.

---

## Author

**Juan Bautista Galisteo Marqués**

Creator and maintainer of **AI Visual Composer**.

---

## Copyright

Copyright © 2026 **Juan Bautista Galisteo Marqués**

All copyright notices and license notices must be preserved in copies or substantial portions of the software in accordance with the MIT License.
