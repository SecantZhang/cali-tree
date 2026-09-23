// Static field reference for the two data shapes a Dataset node emits: the per-item
// `samples` payload (a `JudgeSample`-shaped dict, built by
// vejudge/database/dl_peanut_eval/curate.py::curate_sample) and the joined human `labels`
// payload (an aggregated annotation record, vejudge/database/dl_human_annotations/
// aggregate.py::AggregatedHumanRecord). This is UI reference copy, mirroring the field
// lists documented in vejudge/interface/interface.md — it is NOT introspected from the
// backend at runtime, so keep it in sync with those two source shapes by hand if they change.

export interface SchemaField {
  field: string
  type: string
  description: string
}

// JudgeSample — one sampled dataset item. Nested `input.*`/`output.*` fields are shown
// with their dotted path so the table reads top-to-bottom as the real object shape.
export const JUDGE_SAMPLE_SCHEMA: SchemaField[] = [
  { field: 'item_id', type: 'string', description: 'Canonical join key, `project::prompt_idx::model`. Human labels join to a sample by this exact string.' },
  { field: 'project', type: 'string', description: 'Source project this edit belongs to.' },
  { field: 'prompt_idx', type: 'int', description: 'Which edit prompt within the project.' },
  { field: 'model', type: 'string', description: 'Rendered-output model directory (e.g. `peanut`).' },
  { field: 'use_case', type: 'string', description: 'Edit category: visual montage / speech-driven / voiceover-heavy.' },
  { field: 'input.user_prompt', type: 'string', description: 'The user\'s edit instruction.' },
  { field: 'input.target_duration', type: 'number', description: 'Target output duration, when specified.' },
  { field: 'input.a_roll_transcript_text', type: 'string (JSON)', description: 'A-roll (spoken) transcript pool, serialized.' },
  { field: 'input.b_roll_captions_excerpt', type: 'string (JSON)', description: 'B-roll (visual) clip captions, truncated excerpt.' },
  { field: 'input.b_roll_captions_json_path', type: 'string (path)', description: 'On-disk path to the full B-roll captions file.' },
  { field: 'input.initial_timeline_text', type: 'string', description: 'Any pre-existing timeline text (usually empty).' },
  { field: 'input.notes_path', type: 'string (path)', description: 'Path to the edit notes the assembly was extracted from.' },
  { field: 'input.asset_filepaths', type: 'string[]', description: 'All source-asset paths for the item (clips, maps, config, notes, video).' },
  { field: 'algorithm', type: 'string', description: 'Editing algorithm/model that produced the output (mirrors `model`).' },
  { field: 'output.output_video_path', type: 'string (path)', description: 'Rendered edited video — streamed into the preview player below.' },
  { field: 'output.assembly_json', type: 'object', description: 'Structured edit assembly extracted from the notes.' },
]

// AggregatedHumanRecord — the human labels joined to a sample by `item_id`. `scores` holds
// the per-dimension mean over annotators; a dimension can be null when no annotator rated it.
export const HUMAN_LABEL_SCHEMA: SchemaField[] = [
  { field: 'item_id', type: 'string', description: 'Same `project::prompt_idx::model` key as the sample it labels.' },
  { field: 'n_annotators', type: 'int', description: 'How many annotators rated this item.' },
  { field: 'n_complete', type: 'int', description: 'How many of those annotations were marked complete.' },
  { field: 'scores', type: 'object<dim, number|null>', description: 'Per-dimension mean human score (1–5), null if never rated.' },
  { field: 'score_counts', type: 'object<dim, int>', description: 'How many annotators contributed to each dimension\'s mean.' },
  { field: 'pairwise', type: 'object[]', description: 'Per-annotator overall-ranking preferences, when present.' },
]

// The nine named human-annotation dimensions (aggregate.py::HUMAN_DIMENSIONS), shown as the
// row order for a label's per-dimension scores in the item preview.
export const HUMAN_DIMENSIONS: string[] = [
  'voiceover_matches_visuals',
  'abrupt_cutoffs_voiceover',
  'abrupt_cutoffs_video',
  'story_flow_voiceover',
  'story_flow_visuals',
  'section_placement_opening',
  'section_placement_middle',
  'section_placement_closing',
  'video_addresses_prompt',
]
