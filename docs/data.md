# VEJudge Data Description

VEJudge draws on **two** locations in the research repo. Neither is committed (both are
git-ignored); paths are configurable via env vars in `vejudge/config.py`.

---

## Glossary of shorthand codes

### v1 — First benchmark scope
Throughout this file and `benchmark.md`, **v1** refers to the first shipped scope of the
benchmark: peanut model only, whole-video base64 upload (Strategy A), no calibration fitted
yet (~17 matched items). Limitations are listed in `benchmark.md § Scope & limitations`.

### M1–M6 — The six judge metrics

#### Architecture: one `Judge` class, six prompts, two model backends

All six judges share a single generic runner (`vejudge/core/judge/base_judge.py` — `Judge`
class parametrized by `metric_id`). The per-metric variation lives entirely in the versioned
prompt module (`vejudge/core/prompts/m{n}_*.py`). There is **no separate judge class per
metric**.

```
Judge(metric_id, engine)
  │
  ├─ build_prompt(metric_id, sample)  →  PromptSpec(system, user, schema, version)
  ├─ engine.generate(user, media_inputs, system)  →  raw JSON string
  ├─ parse_json_object(content)
  └─ validate_judge_output(parsed, required_fields)  →  flags / valid bool
```

**Engine routing** (`vejudge/workflow/pipeline.py`, `JudgeEngines.for_metric()`): the
pipeline holds two engines — one text, one video — and dispatches each metric to the right
one based on `JudgeMetric.modality`:

- **M1, M3 → text engine (GPT)** — no media attachment; judge reads text only.
- **M2, M4, M5, M6 → video engine (Gemini)** — rendered MP4 attached as a base64 video
  part via OpenAI-compatible multipart messages.

Both engines share the same abstract base (`lm_engine/lm_template/base.py`): the unified
`generate(prompt, media_inputs, schema, system) → dict` interface, OpenAI-compatible
transport (`openai_compat.py`), and the `llm-histories.log` recorder.

---

#### Metric-by-metric details

Rubric source: `vejudge/core/rubric/definitions.py`. Prompt source: `vejudge/core/prompts/`.

| Code | Name | Component | Engine | Output type | Output schema |
|---|---|---|---|---|---|
| **M1** | Assembly Failure | Plan | GPT (text) | binary gate | `{failure, severity, reasoning_lines[3], evidence[]}` |
| **M2** | Render Failure | Video | Gemini (video) | binary gate | `{failure, severity, reasoning_lines[3], evidence[]}` |
| **M3** | Prompt Completeness | Plan | GPT (text) | 1–5 score | `{score_1_to_5, fully_complete, missing_aspects[], reasoning_lines[3]}` |
| **M4** | Visual Prompt Alignment | Video | Gemini (video) | 1–5 score | `{score_1_to_5, fully_aligned, missing_visual_aspects[], reasoning_lines[3]}` |
| **M5** | Edit Coherence | Video | Gemini (video) | 1–5 score | `{score_1_to_5, issues[], reasoning_lines[3]}` |
| **M6** | AV Sync | Video | Gemini (video) | 1–5 score (× 3 sub) | see M6 sub-dimensions below |

**M1 and M2 are binary failure gates** (not 1–5): they catch catastrophic output before
the scored judges run. M3–M6 produce the 1–5 scores aligned to human annotation dimensions.

The **prompt template is fixed per metric** — identical across all items and all dataset
categories (visual montage / speech-driven / voiceover-heavy). What varies per call is only
the data filled into the template: different `user_prompt`, `assembly_json`, transcript
pool, and video file. `use_case` is never seen by the judge; it is only a postprocessing
breakdown key.

Example scenario used in the prompts below — item `prj-cooking-demo::0::peanut`,
use case `speech-driven`:
> *"Create a 90-second social media reel from this pasta tutorial. Keep Alex's narration
> but swap in B-roll of the pasta and ingredients during the explanation segments.
> End with the finished dish."*

---

**M1 — Assembly Failure** (`m1_assembly_failure.py`, text/GPT)

Judges the **assembly plan** (the orchestrator's notes JSON + structured `assembly_json`),
not the rendered video. This is the only judge with both a system and a user message.

Inputs serialised into the user message as a JSON object:
- `user_prompt` — the edit instruction
- `assembly_json` — final clip IDs, trimmed words, output transcript
- `notes_excerpt` — orchestration history (critic/editor iterations, pipeline status), up to 32 KB
- `a_roll_transcript_excerpt` — source A-roll the editor could pick from, up to 8 KB
- `b_roll_captions_excerpt` — available B-roll visual descriptions, up to 8 KB

`failure=true` means the plan does not target the stated prompt. `severity` provides
graduated detail: `none` (pass), `minor` (mostly addressed, meaningful gap), `major`
(core requirements missing).

*Example prompt (system):*
```
You are an evaluation judge for an automated video assembly system.

Your task: decide whether the ASSEMBLY PLAN (notes JSON + structured assembly_json)
addresses the USER PROMPT. You are judging the *plan*, not the rendered video.

Inputs provided:
- user_prompt: what the user asked for
- assembly_json: final clip IDs, trimmed words, output transcript
- notes_excerpt: orchestration history (critic/editor iterations, pipeline status)
- a_roll_transcript_excerpt: source material the editor could pick from
- b_roll_captions_excerpt: available B-roll visual descriptions

Respond with JSON only (no markdown fences):
{
  "failure": boolean,
  "severity": "none" | "minor" | "major",
  "reasoning_lines": [string, string, string],
  "evidence": [string]
}
- failure=true means the plan does not address the prompt.
- severity: "none" if pass; "minor" if mostly addressed but meaningful gap; "major" if
  clearly wrong or core requirements missing.
- reasoning_lines: exactly 2-3 sentences. (1) What in the assembly/notes you observed.
  (2) How that maps to the prompt requirements. (3) Why that implies pass or fail.
```

*Example prompt (user message — JSON-serialised):*
```json
{
  "user_prompt": "Create a 90-second social media reel from this pasta tutorial. Keep Alex's narration but swap in B-roll of the pasta and ingredients during the explanation segments. End with the finished dish.",
  "assembly_json": {
    "clips": [
      {"clip_id": "vid-001-s3", "type": "a_roll", "speaker": "Alex", "start_word": 0,  "end_word": 18},
      {"clip_id": "vid-003-b1", "type": "b_roll", "caption": "flour being poured onto wooden board"},
      {"clip_id": "vid-001-s5", "type": "a_roll", "speaker": "Alex", "start_word": 19, "end_word": 41},
      {"clip_id": "vid-003-b3", "type": "b_roll", "caption": "eggs cracked into flour well"},
      {"clip_id": "vid-001-s9", "type": "a_roll", "speaker": "Alex", "start_word": 84, "end_word": 102},
      {"clip_id": "vid-003-b7", "type": "b_roll", "caption": "finished pasta dish plated with garnish"}
    ],
    "output_transcript": "Today we're making fresh pasta. You'll need '00' flour and two eggs per serving. Make a well in the flour, crack in the eggs, and mix from the centre outward. Knead for ten minutes. Let it rest, roll thin, cut, and plate — buon appetito!"
  },
  "notes_excerpt": "{\"stage\": \"OrchestratorRefineV2\", \"iterations\": [{\"critic\": \"Missing B-roll during ingredient explanation; narration gap between s5 and s9.\", \"editor\": \"Inserted vid-003-b3 at 00:24. Trimmed s9 start by 1.2s to close gap.\"}], \"status\": \"complete\"}",
  "a_roll_transcript_excerpt": "[{\"clip_id\": \"vid-001-s3\", \"speaker\": \"Alex\", \"text\": \"Today we're making fresh pasta.\"}, {\"clip_id\": \"vid-001-s5\", \"speaker\": \"Alex\", \"text\": \"You'll need '00' flour and two eggs per serving.\"}, {\"clip_id\": \"vid-001-s9\", \"speaker\": \"Alex\", \"text\": \"Plate it up — buon appetito!\"}]",
  "b_roll_captions_excerpt": "[{\"clip_id\": \"vid-003-b1\", \"caption\": \"flour being poured onto wooden board\"}, {\"clip_id\": \"vid-003-b3\", \"caption\": \"eggs cracked into flour well\"}, {\"clip_id\": \"vid-003-b5\", \"caption\": \"pasta dough being kneaded by hand\"}, {\"clip_id\": \"vid-003-b7\", \"caption\": \"finished pasta dish plated with garnish\"}]"
}
```

---

**M2 — Render Failure** (`m2_render_failure.py`, video/Gemini)

Watches the rendered MP4 and decides whether it is **broken or unwatchable**. No system
message — the full task is in the user turn. Failure threshold is intentionally high:
minor quality issues are not failures. `failure=true` requires a broken/corrupt/black
video or content completely unrelated to the prompt.

Inputs: `user_prompt` (embedded in prompt text) + rendered MP4 (video attachment).

*Example prompt (user message + video):*
```
You are an evaluation judge for an automated video editing system.

Watch the attached video and decide whether it is a FAILURE.

User prompt that the video should address:
"Create a 90-second social media reel from this pasta tutorial. Keep Alex's narration
but swap in B-roll of the pasta and ingredients during the explanation segments.
End with the finished dish."

A failure means:
- The video is broken, black, corrupt, or unwatchable
- The video content is completely unrelated to the prompt
- Severe audio/visual glitches that make it unusable

A NON-failure means the video is watchable and makes a reasonable attempt at the prompt,
even if imperfect. Minor quality issues are NOT failures.

Respond with JSON only (no markdown fences):
{
  "failure": boolean,
  "severity": "none" | "minor" | "major",
  "reasoning_lines": [string, string, string],
  "evidence": [string]
}
- reasoning_lines: exactly 2-3 sentences describing what you see, how it relates to the
  prompt, and why it passes or fails.

[MEDIA: 20250601_143022_prompt_0_final.mp4]
```

---

**M3 — Prompt Completeness** (`m3_prompt_completeness.py`, text/GPT)

Scores whether the **assembly plan satisfies every part of the user prompt** (1–5). The
system message embeds the metric definition from `rubric/definitions.py` verbatim (the
only judge that does this). Inputs serialised as a JSON object in the user message:
- `user_prompt`
- `source_a_roll_pool_excerpt` — full source transcript pool the editor had to pick from, up to 24 KB
- `assembly_json` — the selected clips and output transcript
- `initial_timeline_text_head` — first 4 KB of the assembled timeline text

Scoring: 5 = every explicit content requirement covered; 4 = minor gap; 3 = important
aspect missing; 2 = mostly off-brief; 1 = unrelated or empty.

*Example prompt (system):*
```
You are an MLLM-as-judge evaluator for video assembly quality.

Metric: Prompt completeness (text-only evaluation of the assembly plan)
Definition from the project metric catalog:
Given source transcript, captions, and user prompt, does the assembled plan satisfy every
part of the request? Scored 1-5.
Measures: Whether the assembly covers the full user prompt, not just a subset.

You are given the user prompt, the pool of source A-roll transcript data (what could
be selected from), and the structured output assembly (selected clips, final word-level
view, output transcript). You are judging the PLAN, not watching a video.

Task: Decide whether the assembly satisfies *every part* of the user request that pertains
to content selection and inclusion. If the prompt demands edits you cannot verify from text
(e.g. exact duration), estimate from transcript length and timeline hints.

Respond with JSON only (no markdown fences):
{
  "score_1_to_5": integer,
  "fully_complete": boolean,
  "missing_aspects": [string],
  "reasoning_lines": [string, string, string]
}
Scoring rubric:
- 5: Every explicit content requirement in the prompt is reflected in the assembly.
- 4: Minor gap or ambiguity -- one small aspect weakly covered.
- 3: Important aspect missing or only partially covered.
- 2: Mostly off-brief -- assembly addresses a different goal.
- 1: Unrelated or empty.
- fully_complete: true only if score is 5.
- reasoning_lines: exactly 2-3 sentences. List prompt requirements, trace to assembly
  evidence, state why the score follows.
```

*Example prompt (user message — JSON-serialised):*
```json
{
  "user_prompt": "Create a 90-second social media reel from this pasta tutorial. Keep Alex's narration but swap in B-roll of the pasta and ingredients during the explanation segments. End with the finished dish.",
  "source_a_roll_pool_excerpt": "[{\"clip_id\": \"vid-001-s1\", \"speaker\": \"Alex\", \"text\": \"Welcome back to my kitchen.\"}, {\"clip_id\": \"vid-001-s3\", \"speaker\": \"Alex\", \"text\": \"Today we're making fresh pasta from scratch.\"}, {\"clip_id\": \"vid-001-s5\", \"speaker\": \"Alex\", \"text\": \"You'll need '00' flour and two eggs per serving.\"}, {\"clip_id\": \"vid-001-s7\", \"speaker\": \"Alex\", \"text\": \"Knead the dough for about ten minutes until smooth and elastic.\"}, {\"clip_id\": \"vid-001-s9\", \"speaker\": \"Alex\", \"text\": \"Plate it up — buon appetito!\"}]",
  "assembly_json": {
    "clips": [
      {"clip_id": "vid-001-s3", "type": "a_roll", "speaker": "Alex", "start_word": 0,  "end_word": 18},
      {"clip_id": "vid-003-b1", "type": "b_roll", "caption": "flour being poured onto wooden board"},
      {"clip_id": "vid-001-s5", "type": "a_roll", "speaker": "Alex", "start_word": 19, "end_word": 41},
      {"clip_id": "vid-003-b3", "type": "b_roll", "caption": "eggs cracked into flour well"},
      {"clip_id": "vid-001-s9", "type": "a_roll", "speaker": "Alex", "start_word": 84, "end_word": 102},
      {"clip_id": "vid-003-b7", "type": "b_roll", "caption": "finished pasta dish plated with garnish"}
    ],
    "output_transcript": "Today we're making fresh pasta. You'll need '00' flour and two eggs per serving. Make a well in the flour, crack in the eggs, and mix from the centre outward. Knead for ten minutes. Let it rest, roll thin, cut, and plate — buon appetito!"
  },
  "initial_timeline_text_head": ""
}
```

---

**M4 — Visual Prompt Alignment** (`m4_visual_alignment.py`, video/Gemini)

Watches the rendered MP4 and scores whether the **on-screen content visually matches the
prompt** (1–5). No system message. Evaluates what appears on screen vs. what was asked:
B-roll choices, A-roll presence, timing if the prompt specifies duration. Mirrors M3
(which judges the plan) but from the rendered video.

Inputs: `user_prompt` (embedded in prompt text) + rendered MP4 (video attachment).

*Example prompt (user message + video):*
```
You are an evaluation judge for an automated video editing system.

Watch the attached video and score how well it visually fulfills the user's prompt.

User prompt:
"Create a 90-second social media reel from this pasta tutorial. Keep Alex's narration
but swap in B-roll of the pasta and ingredients during the explanation segments.
End with the finished dish."

Evaluate whether what appears on screen matches the prompt:
- Does the video show the content the user asked for?
- Are visual elements (B-roll, A-roll, cuts) aligned with the request?
- Does timing/duration match if the prompt specifies it?

Respond with JSON only (no markdown fences):
{
  "score_1_to_5": integer,
  "fully_aligned": boolean,
  "missing_visual_aspects": [string],
  "reasoning_lines": [string, string, string]
}
Scoring rubric:
- 5: Every visual requirement met. What's on screen is exactly what the prompt asked for.
- 4: Minor gap -- mostly aligned but one small visual aspect missing or weak.
- 3: Important visual aspect missing or only partially shown.
- 2: Mostly off-brief -- video shows different content than requested.
- 1: Completely unrelated or empty.
- fully_aligned: true only if score is 5.
- reasoning_lines: exactly 2-3 sentences. What you see vs what was asked vs your score.

[MEDIA: 20250601_143022_prompt_0_final.mp4]
```

---

**M5 — Edit Coherence** (`m5_edit_coherence.py`, video/Gemini)

Watches the rendered MP4 and scores **flow, pacing, and watchability** (1–5). No system
message. The `user_prompt` provides audience/genre context (e.g. "social media reel" tells
the judge to expect snappy pacing). Evaluates: clip transitions, pacing, audio continuity,
overall watchability.

Inputs: `user_prompt` (embedded in prompt text) + rendered MP4 (video attachment).

*Example prompt (user message + video):*
```
You are an evaluation judge for an automated video editing system.

Watch the attached video and score the EDIT COHERENCE -- how well it flows as a
watchable piece of content.

User prompt (for audience/context):
"Create a 90-second social media reel from this pasta tutorial. Keep Alex's narration
but swap in B-roll of the pasta and ingredients during the explanation segments.
End with the finished dish."

Evaluate:
- Flow: do clips transition smoothly without jarring jumps?
- Pacing: is the rhythm appropriate for the stated audience (e.g. "social media" = snappy)?
- Audio continuity: does the voiceover/dialogue flow naturally without awkward cuts?
- Watchability: would a viewer find this engaging and easy to follow?

Respond with JSON only (no markdown fences):
{
  "score_1_to_5": integer,
  "issues": [string],
  "reasoning_lines": [string, string, string]
}
Scoring rubric:
- 5: Professional quality -- smooth flow, good pacing, clean audio, highly watchable.
- 4: Good overall but one minor issue (e.g. slightly awkward transition).
- 3: Noticeable issues that hurt watchability (e.g. choppy pacing, abrupt cuts).
- 2: Multiple issues -- hard to watch, disjointed, poor audio continuity.
- 1: Unwatchable -- no coherent flow.
- reasoning_lines: exactly 2-3 sentences. What you observed, what works/doesn't, your score.

[MEDIA: 20250601_143022_prompt_0_final.mp4]
```

---

**M6 — AV Sync** (`m6_av_sync.py`, video/Gemini)

Watches the rendered MP4 and scores **audio-visual synchronization** across three
sub-dimensions, each scored 1–5. No system message — the full rubric (including all three
sub-dimension criteria) is in the user turn, making it the longest single prompt.
`overall_av_sync_score` = average of 6a/6b/6c, rounded.

Inputs: `user_prompt` (embedded in prompt text) + rendered MP4 (video attachment).

| Sub-code | Name | What it checks | Scoring anchor |
|---|---|---|---|
| **M6a** | Voiceover-Visual Match | Does voiceover content match the A-roll/B-roll on screen at that moment? | 5 = well-matched throughout; 1 = severe mismatch |
| **M6b** | Voiceover Continuity | Sudden pauses, awkward silences, mid-sentence cuts, audio pops | 5 = natural flow; 1 = severely broken audio |
| **M6c** | Visual Continuity | Freeze frames, black frames, repeated shots, extreme jump cuts | 5 = clean transitions; 1 = unwatchable visual track |

*Example prompt (user message + video):*
```
You are a specialist audio-visual quality judge for an automated video editing system.

Watch the attached video carefully with attention to both the AUDIO (voiceover/dialogue)
and the VISUALS (A-roll talking-head footage and B-roll cutaway footage). The video was
assembled by an algorithm in response to this user prompt:

"Create a 90-second social media reel from this pasta tutorial. Keep Alex's narration
but swap in B-roll of the pasta and ingredients during the explanation segments.
End with the finished dish."

Evaluate these three specific dimensions:

## 6a. Voiceover-Visual Match
Does the voiceover/dialogue content match what is shown on screen at the same time?
- When the speaker talks about a specific topic (e.g. "cutting onions"), is relevant
  footage (A-roll of them speaking or B-roll of onion cutting) shown?
- Are B-roll cutaway clips topically aligned with the voiceover playing over them?
- Major mismatches: voiceover about topic X while showing completely unrelated footage.

## 6b. Voiceover Continuity
Are there sudden pauses, awkward silences, abrupt mid-sentence cuts, or audio glitches
in the voiceover/dialogue track?
- Smooth: sentences flow naturally, no jarring gaps.
- Problematic: mid-word cuts, unnatural silence gaps (>1s) between sentences that were
  clearly stitched, audio pops or repeated words from bad splicing.

## 6c. Visual Continuity
Are there sudden pauses, freeze frames, black frames, repeated shots, or jarring visual
jump cuts in the video track?
- Smooth: cuts feel intentional, no frozen or black frames, clips transition cleanly.
- Problematic: freeze frames, black flashes between clips, identical shot repeated
  back-to-back, extreme jump cuts within the same clip.

Respond with JSON only (no markdown fences):
{
  "voiceover_visual_match": {
    "score_1_to_5": integer,
    "issues": [string],
    "reasoning": string
  },
  "voiceover_continuity": {
    "score_1_to_5": integer,
    "issues": [string],
    "reasoning": string
  },
  "visual_continuity": {
    "score_1_to_5": integer,
    "issues": [string],
    "reasoning": string
  },
  "overall_av_sync_score": integer,
  "reasoning_lines": [string, string, string]
}

Scoring rubric (each sub-dimension):
- 5: No issues detected -- smooth and well-matched throughout.
- 4: One minor issue that a casual viewer might not notice.
- 3: Noticeable issue that detracts from the viewing experience.
- 2: Multiple issues -- feels poorly assembled.
- 1: Severely broken -- unwatchable audio or visual track.

overall_av_sync_score: average of the three, rounded to nearest integer.
reasoning_lines: 2-3 sentences summarizing the biggest AV concerns (or lack thereof).

[MEDIA: 20250601_143022_prompt_0_final.mp4]
```

---

| Location | Default path | What it holds |
|---|---|---|
| **Source data** | `data/` (`VEJUDGE_DATA_ROOT`) | Per-project source clips, transcripts, captions, edit instructions. |
| **Evaluation data** | `evaluation/` (`VEJUDGE_EVALUATION_ROOT`) | Rendered model outputs + human annotations of those outputs. |

The benchmark joins the two: it judges a **rendered output video** (from `evaluation/`)
against the **edit instruction + source material** (from `data/`), then compares the judge
scores to the **human annotations** of the same video.

### Rendered-output layouts (per model)

Three models are human-annotated — **peanut, coconut, grapenut** (34 labeled items total:
13 / 12 / 9). They share the annotation format but render to **different on-disk trees**
under `RENDERED_ROOT/<alias>/<project>/`, so `video_resolver` dispatches on
`config.MODEL_LAYOUT`:

| model | layout | `prompt_idx N →` | assembly source |
|---|---|---|---|
| peanut | `videos/*prompt_{N}_final.mp4` + `notes/` + `otio/` | glob `prompt_{N}` | `notes.json` |
| coconut | `{NNN}/render.mp4` + `timeline.otio` + `plan.md` | `{N+1:03d}/` (ordinal run subdir) | OTIO |
| grapenut | `videos/{N}_video.mp4` + `otio/{N}_timeline.otio` | `{N}_video.mp4` | OTIO |

Notes: coconut/grapenut have no `notes.json`, so the assembly comes from the OTIO timeline
(`extract_assembly_from_otio`, best-effort; the video judge scores from the render
regardless). The coconut ordinal mapping (`NNN → prompt NNN-1`) is inferred — the resolver
warns if a project's run subdirs aren't contiguous `001..00N`. 33 of the 34 labeled items
resolve with video (grapenut `prj-paris-2025` has no render). Source assets in `data/` are
model-agnostic, so the edit instruction/transcript resolve for every model.

### VE-Bench DB (public — a separate calibration track)

`VEBENCH_ROOT` (default `data/ve-bench/VE-Bench-DB/`) holds the public VE-Bench quality set:
**~1,170 edited videos from 8 text-driven-editing methods over 169 source videos, each with
a human MOS (scale 1–10) from 24 annotators**. Layout:

```
label.txt                       # "<file>.mp4|<human_MOS>|<edit_prompt>" per line
train_samples/edited/<file>.mp4  # the edited (output) video   -> output_video_path
train_samples/src/<file>.mp4     # the source video (same stem) -> source_video_path asset
```

`dl_vebench.VeBenchLoader` maps each to a JudgeSample (item id `<stem>::0::vebench`, edit
prompt → `user_prompt`); `materialize_vebench_labels()` writes each MOS as a per-item
`*_humaneval.json` under `HUMAN_ANNOTATIONS_ROOT/vebench/` on the `edit_quality` dimension,
so the standard Dataset node picks up VE-Bench labels by item id (no graph change). This is
**appearance/content editing, not peanut's assembly editing** — a separate calibration track
anchored on the single `edit_quality` MOS (its own 1–10 scale; calibration learns the map
from the judge's score). VE-Bench ships only the aggregated MOS (no per-rater breakdown), so
its `edit_quality` has one "annotator" and no inter-rater ceiling.

Note: VEFX-Bench was evaluated but **not** ingested — its public release is source videos +
instructions + a reward *model* (no released human scores or edited outputs), so it isn't a
human-scored calibration set.

---

## 1. Source data — `data/<project>/`

~36 `prj-*` projects. Each is a short-form video editing task: a pool of source clips plus
a natural-language edit instruction. Editing here means **stitching/selecting clips**, not
generating or restyling footage.

| File | Schema (key fields) | Used by |
|---|---|---|
| `user_query.json` | `prompts[].user_request` (instruction), `prompts[].target_duration` (sec) | judge prompts (the brief) |
| `video_id_map.json` | `{video_id: {name, walnut_id, duration_ms}}` | asset metadata |
| `all_visual_clips.json` | `[{video_id, clip_id, start_time, end_time, caption, tags[]}]` | B-roll captions for text judges |
| `all_sentences.json` | `[{video_id, clip_id, inTimeMS, outTimeMS, speaker, text}]` | A-roll transcript pool for text judges |
| `all_sentences_and_words.json` | `{sentences[], words[]}` (word-level timing) | (available; not used in v1) |
| `videos/` | source MP4s | (not uploaded in v1) |
| `raw-visual-segments/`, `raw-transcripts/` | per-video versions of the above | (source for the aggregated files) |
| `sb-dag/`, `otio/` | StoryBoard DAG / OpenTimelineIO edit definitions | (reference; not used in v1) |
| `processing-logs/` | per-video job results (status, URLs, auth tokens) | (ignored) |

**Project categories** come from `data/use_cases_config.json`:
`{project: {a_roll_files, b_roll_files, use_case}}` where `use_case ∈ {visual montage,
speech-driven, voiceover-heavy}`. VEJudge uses `use_case` as the per-category breakdown key.

There are **no human scores in `data/`** — those live in `evaluation/` (below).

---

## 2. Rendered outputs — `evaluation/all models output/<model>/<project>/`

The videos that humans rated, produced by several editing models: `coconut`, `peanut`
(dir `peanut-v4-multi-track-gpt-5-1-medium`), `grapenut`, `loopedit`.

**peanut layout (v1 target — clean and complete):**
```
peanut-v4-multi-track-gpt-5-1-medium/<project>/
├── videos/<ts>_prompt_<idx>_final.mp4     # the rendered video
├── notes/<ts>_prompt_<idx>_notes.json     # orchestration history -> assembly plan
└── otio/<ts>_prompt_<idx>_final.otio       # timeline
```
The notes JSON contains an `OrchestratorRefineV2` stage from which the assembly plan
(final clip ids, trimmed words, word-level timeline) is extracted for the **text** judges
(M1, M3). `coconut`/`grapenut`/`loopedit` use numbered folders without notes and need fuzzy
prompt↔folder resolution — **out of scope for v1**.

---

## 3. Human annotations — `evaluation/human_annotations/<project>/`

287 files, ~22 annotators, 8 projects. One file = one annotator rating one
`(project, prompt_idx, model, output_slot)`. Filename:
`<annotator>_..._prompt<idx>_<project>_<model>_<uuid>_humaneval.json`.

**Top level:** `annotator, project, model, prompt_idx, cell_key, output_slot, output_label,
timestamp, metric_complete, annotation`.

**`annotation` block** — scores are **strings** `"1".."5"` or `""` (not rated):

| Field | Scale | Aligned judge signal |
|---|---|---|
| `video_addresses_prompt` | 1–5 | M3 (prompt completeness) |
| `voiceover_matches_visuals` | 1–5 | M6a (voiceover-visual match) |
| `abrupt_cutoffs_voiceover` | 1–5 | M6b (voiceover continuity) |
| `abrupt_cutoffs_video` | 1–5 | M6c (visual continuity) |
| `story_flow_voiceover` / `story_flow_visuals` | 1–5 | M5 (edit coherence) |
| `section_placement_opening/middle/closing` | 1–5 | M5 (edit coherence) |
| `overall_ranking` | "1"/"2" (pairwise) | derived overall (pairwise accuracy) |

Plus free-text (`other_anomalies`, `*_note`), emotion tags, per-metric time/difficulty,
optional `timestamp_annotations[]`, and `_complete` (only ~29% of files are complete).
Multiple annotators per item are **averaged** per dimension (empty strings dropped); see
`vejudge/database/dl_human_annotations/aggregate.py`.

---

## 4. How the pieces join

```
data/<project>/user_query.json   ─┐  (instruction, target_duration)
data/<project>/all_sentences.json ┤→  curate JudgeSample.input  ─┐
data/<project>/all_visual_clips.json ┘                          │
                                                                ├→ judges → scores
evaluation/all models output/<model>/<project>/videos/...mp4 ──┘  (rendered output)
                                                                       │
evaluation/human_annotations/<project>/...humaneval.json ───→ aggregated human scores
                                                                       │
                                          align by item_id "project::prompt_idx::model"
```

The canonical **item id** is `"<project>::<prompt_idx>::<model>"`, produced by both the
peanut loader (`dl_peanut_eval`) and the human-annotation aggregator
(`dl_human_annotations`). The benchmark evaluates the intersection of the two.

In v1 (peanut only), **17 items** have both a rendered video and human annotations.
