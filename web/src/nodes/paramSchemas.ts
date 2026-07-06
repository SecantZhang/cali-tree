// Static mirror of the backend's param_schema dicts (dataset_node.py / judge_node.py /
// eval_node.py). Drives the Inspector's schema-driven form. Keep in sync with the
// backend; task-11-era work may switch this to be fetched live from GET /api/nodes.

export type ParamFieldType = 'string' | 'number' | 'bool' | 'enum' | 'list[string]' | 'list[enum]'

export interface ParamField {
  type: ParamFieldType
  default: unknown
  options?: string[]
  min?: number
  max?: number
}

export const NODE_PARAM_SCHEMAS: Record<string, Record<string, ParamField>> = {
  dataset: {
    loader: {
      type: 'enum', options: ['human_annotations', 'peanut_eval'], default: 'peanut_eval',
    },
    model: { type: 'string', default: 'peanut' },
    projects: { type: 'list[string]', default: null },
    sampling_ratio: { type: 'number', default: 1.0, min: 0, max: 1 },
    sampling_mode: {
      type: 'enum', options: ['full', 'unified', 'stratified'], default: 'full',
    },
    use_case_filter: { type: 'list[string]', default: null },
    item_id_pattern: { type: 'string', default: null },
  },
  judge: {
    metrics: {
      type: 'list[enum]', options: ['M1', 'M2', 'M3', 'M4', 'M5', 'M6'], default: null,
    },
    skip_video: { type: 'bool', default: false },
    text_engine_kind: { type: 'enum', options: ['gpt', 'qwen'], default: 'gpt' },
    text_model: { type: 'string', default: null },
    video_engine_kind: { type: 'enum', options: ['gemini'], default: 'gemini' },
    video_model: { type: 'string', default: null },
    temperature: { type: 'number', default: null },
  },
  eval: {},
}

export function defaultParamsFor(nodeType: string): Record<string, unknown> {
  const schema = NODE_PARAM_SCHEMAS[nodeType] ?? {}
  const params: Record<string, unknown> = {}
  for (const [key, field] of Object.entries(schema)) {
    params[key] = field.default
  }
  return params
}
