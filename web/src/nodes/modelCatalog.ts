// Model catalog grouped by provider-accurate engine_kind, mirroring the backend's
// `_ENGINES` registry (vejudge/lm_engine/__init__.py) — the model string itself is never
// validated by the backend (pure pass-through to the gateway), so this list exists purely
// to drive the LM Engine Node's model dropdown, scoped to whichever engine_kind is
// currently selected.
export const MODELS_BY_ENGINE_KIND: Record<string, string[]> = {
  gemini: [
    'gemini-2.5-flash',
    'gemini-2.5-flash-image',
    'gemini-2.5-flash-lite',
    'gemini-2.5-pro',
    'gemini-3-pro-image-preview',
    'gemini-3-pro-preview',
    'gemini-3.1-flash-image-preview',
    'gemini-3.1-flash-lite-preview',
    'gemini-3.1-pro-preview',
    'gemini-3.5-flash',
    'gemma-4-31B-it',
    'vertex_ai/veo-3.1-fast-generate-001',
    'vertex_ai/veo-3.1-generate-001',
  ],
  gpt: [
    'gpt-4.1',
    'gpt-4.1-mini',
    'gpt-4.1-nano',
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-5',
    'gpt-5-chat',
    'gpt-5-mini',
    'gpt-5-nano',
    'gpt-5-pro',
    'gpt-5.1',
    'gpt-5.2',
    'gpt-5.2-chat',
    'gpt-5.2-codex',
    'gpt-5.3-chat',
    'gpt-5.3-codex',
    'gpt-5.4',
    'gpt-5.4-mini',
    'gpt-5.4-nano',
    'gpt-5.4-pro',
    'gpt-5.5',
    'gpt-image-1',
    'gpt-image-1-mini',
    'gpt-image-1.5',
    'gpt-image-2',
    'gpt-oss-120b',
    'gpt-oss-20b',
    'o4-mini',
    'text-embedding-3-large',
    'text-embedding-3-small',
  ],
  qwen: ['qwen-3.5-397b-a17b-FP8'],
  claude: [
    'claude-haiku-4.5',
    'claude-opus-4.5',
    'claude-opus-4.6',
    'claude-opus-4.7',
    'claude-opus-4.8',
    'claude-sonnet-4.5',
    'claude-sonnet-4.6',
  ],
  deepseek: ['deepseek-r1'],
  llama: ['llama-3-1-8b', 'llama-3-2-90b-vision', 'llama-3-3-70b'],
  kimi: ['kimi-k2.5'],
}

export function modelsFor(engineKind: string): string[] {
  return MODELS_BY_ENGINE_KIND[engineKind] ?? []
}
