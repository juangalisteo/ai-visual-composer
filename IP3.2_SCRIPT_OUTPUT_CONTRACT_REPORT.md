# IP3.2 Script Output Contract Report

## Phase

`IP3.2 - Script Generation Output Contract and LLM Response Sanitization`

## Objective

Prevent conversational LLM responses from entering AI Visual Composer as script content.

The observed failure was assistant-style text such as `Answer`, `Word count`, and `This response` propagating into voice, subtitles, storyboard, Visual Intelligence, Prompt Translation, and image generation.

## Root Cause

The contamination point was the boundary between the raw LLM response and the internal script contract.

Audited path:

```text
PromptEngine.build_script_prompt
  -> ScriptBuilder.build
  -> OllamaProvider.generate
  -> response.json()["response"]
  -> script string
  -> VoiceBuilder
  -> SubtitleBuilder
  -> StoryboardBuilder
```

Findings:

- `OllamaProvider` returns the raw Ollama `response` field.
- No repository parser was adding `Answer`, `Word count`, or assistant comments.
- `ScriptBuilder` accepted raw LLM output as plain text.
- `cargar_o_generar_guion` wrote that raw text to `scripts/guion.txt`.
- Downstream components consumed the file as authoritative script content.

Therefore the root cause was missing output governance at `ScriptBuilder`.

## New Contract

`ScriptGenerationResult` is now the structured boundary between raw LLM output and the runtime.

Only this field may continue downstream:

```text
ScriptGenerationResult.script
```

Metadata remains outside voice, subtitles, storyboard, Visual Intelligence, Prompt Translation, images, and video.

## New Validator

`ScriptOutputValidator` rejects:

- empty script;
- invalid UTF-8;
- length outside the accepted narrative range;
- Markdown;
- code fences;
- assistant headings such as `Answer`, `Response`, `Output`, and `Final answer`;
- `Word count` metadata;
- model comments;
- accidental JSON;
- accidental XML.

The length validator applies a controlled 20% tolerance because the prompt describes the word range as approximate, while still rejecting clearly excessive outputs.

## Controlled Retry

Maximum attempts:

```text
2
```

Attempt 1 uses the normal script prompt.

Attempt 2 uses a minimal corrective prompt containing:

- the fact that the previous response violated the required format;
- the validation reason;
- the topic;
- the valid word range;
- the exact target word count;
- the output constraints.

The invalid response is never concatenated, cleaned, or reused.

## Error Contract

If both attempts fail, `InvalidScriptOutputError` is raised.

Error code:

```text
INVALID_SCRIPT_OUTPUT
```

The error includes:

- reason;
- invalid field;
- original response;
- parser id;
- model;
- prompt id.

The pipeline stops before writing invalid script content.

## Files Reviewed

- `app/core/prompt_engine.py`.
- `app/modules/script/script_builder.py`.
- `app/providers/ollama_provider.py`.
- `app/core/start.py`.
- `app/modules/audio/voice_builder.py`.
- `app/modules/subtitles/subtitle_builder.py`.
- `app/modules/storyboard/storyboard_builder.py`.
- `app/modules/storyboard/storyboard_response_parser.py`.
- `prompts/tasks/script.txt`.
- `prompts/tasks/storyboard.txt`.
- related runtime and image pipeline tests.

## Files Modified

- `app/core/prompt_engine.py`.
- `app/core/start.py`.
- `app/modules/script/__init__.py`.
- `app/modules/script/models.py`.
- `app/modules/script/script_builder.py`.
- `app/modules/script/validator.py`.
- `tests/test_script_output_contract.py`.
- `README.md`.
- `ARCHITECTURE.md`.
- `CHANGELOG.md`.
- `ROADMAP.md`.
- `IP3.2_SCRIPT_OUTPUT_CONTRACT_REPORT.md`.

## Tests

Added:

- `tests/test_script_output_contract.py`.

Coverage:

- valid response;
- `Answer` heading;
- `Word count`;
- model explanation;
- Markdown;
- JSON;
- XML;
- empty response;
- too long response;
- too short response;
- mixed-language model comment;
- model comments;
- retry success;
- structured failure;
- invalid LLM output not written for storyboard.

## Real Validation

Ollama was available locally:

```text
http://localhost:11434
model: qwen3:14b
```

The LLM initially produced clean narrative text that exceeded the requested short duration range. The contract correctly rejected it and stopped the pipeline with `INVALID_SCRIPT_OUTPUT`.

After retry prompt governance was corrected, a valid real script was accepted:

```text
La Ley del Mentalismo: la mente es la fuerza primaria del universo. Todo pensamiento, intención y creencia materializa la realidad. La mente, transforma el mundo.
```

Evidence:

- word count: `26`;
- no `Answer`;
- no `Word count`;
- no `This response`;
- no Markdown;
- no JSON;
- no XML.

## Downstream Validation

Full voice/subtitle validation could not be completed because Edge TTS network access was denied by the environment:

```text
Cannot connect to host speech.platform.bing.com:443 [Acceso denegado]
```

An escalated rerun was requested but rejected because it would send script text to an external service. No workaround was attempted.

A safe downstream validation was executed without external voice:

```text
script: real accepted LLM script
voice: disabled
subtitles: disabled
storyboard: enabled
images: enabled
video: disabled
```

Storyboard and image generation completed successfully using the real accepted script.

Evidence:

- storyboard: `output/ip3_2_real_validation_downstream/storyboard/storyboard.json`;
- image manifest: `output/ip3_2_real_validation_downstream/images/images_manifest.json`;
- image: `output/ip3_2_real_validation_downstream/images/scene_001.png`;
- forbidden markers in script/storyboard/manifest: none.

## Validation Commands

Completed before final report:

- `python -m unittest tests.test_script_output_contract`: `17` tests, OK.
- targeted integration block: `38` tests, OK.
- `python -m unittest discover`: `606` tests, OK.
- `python -m compileall app tests certification`: OK.
- `git diff --check`: OK.

Final validation must be rerun after documentation updates.

## Architectural Guarantees

- Image Runtime architecture was not changed.
- Visual Intelligence contracts were not changed.
- Prompt Translation was not changed.
- ComfyUI workflow was not changed.
- Image Pipeline visual behavior was not changed.
- Video Pipeline behavior was not changed.
- The raw LLM response is no longer treated as free text.
- Only validated `ScriptGenerationResult.script` may enter downstream runtime stages.

## Status

`IP3_2_SCRIPT_OUTPUT_CONTRACT_BLOCKED`

Blocking reason:

- real Voice/Subtitles validation requires Edge TTS network access, which was denied by the execution environment.
