// Human-readable node titles keyed by node type — the single authority, shared by the
// top-bar RunProgress bars and the LM Engine secondary tab's "feeds" list (and anywhere
// else that needs to name a node by its type). Falls back to the raw type string when a
// type isn't listed (e.g. a future node type not yet added here).
export const NODE_TITLE_FOR_TYPE: Record<string, string> = {
  peanut_source: 'Peanut Source',
  dataset: 'Dataset',
  preprocessing: 'Preprocessing',
  lm_engine: 'LM Engine',
  judge_prompt: 'Judge Prompt',
  judge: 'Judge',
  eval: 'Eval',
}

export function nodeTitle(type: string | undefined): string {
  return (type && NODE_TITLE_FOR_TYPE[type]) || type || 'node'
}
