import { expect, test } from '@playwright/test'
import { waitForPaletteLoaded } from '../helpers'

const API_BASE = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8611'

test.describe('Cali-Tree image workflow', () => {
  test('registers the workbench nodes and dry-runs source → train → route → eval', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)
    for (const label of [
      'imagenhub_source', 'calitree_train', 'rubric_lite_train', 'calitree_judge', 'calitree_eval',
    ]) {
      await expect(page.locator('.node-palette-item', { hasText: label })).toBeVisible()
    }

    const graph = {
      nodes: [
        { id: 'source', type: 'imagenhub_source', params: { repeat: 1 } },
        { id: 'dataset', type: 'dataset', params: { full_dataset: true } },
        { id: 'judge_engine', type: 'lm_engine',
          params: { engine_kind: 'gpt', model: 'mock-image-judge', max_tokens: 128 } },
        { id: 'optimizer_engine', type: 'lm_engine',
          params: { engine_kind: 'gpt', model: 'mock-optimizer', max_tokens: 128 } },
        { id: 'train', type: 'calitree_train',
          params: { embedding_model: 'mock-embedding', max_steps: 3 } },
        { id: 'route', type: 'calitree_judge', params: {} },
        { id: 'eval', type: 'calitree_eval', params: {} },
      ],
      edges: [
        { source: 'source', source_socket: 'raw_dataset', target: 'dataset', target_socket: 'raw_dataset' },
        { source: 'source', source_socket: 'raw_labels', target: 'dataset', target_socket: 'raw_labels' },
        { source: 'dataset', source_socket: 'samples', target: 'train', target_socket: 'samples' },
        { source: 'dataset', source_socket: 'labels', target: 'train', target_socket: 'labels' },
        { source: 'judge_engine', source_socket: 'engine_config', target: 'train', target_socket: 'judge_engine' },
        { source: 'optimizer_engine', source_socket: 'engine_config', target: 'train', target_socket: 'optimizer_engine' },
        { source: 'dataset', source_socket: 'samples', target: 'route', target_socket: 'samples' },
        { source: 'train', source_socket: 'prompt_tree', target: 'route', target_socket: 'prompt_tree' },
        { source: 'judge_engine', source_socket: 'engine_config', target: 'route', target_socket: 'judge_engine' },
        { source: 'route', source_socket: 'judge_result', target: 'eval', target_socket: 'judge_result' },
        { source: 'dataset', source_socket: 'labels', target: 'eval', target_socket: 'labels' },
        { source: 'dataset', source_socket: 'samples', target: 'eval', target_socket: 'samples' },
      ],
    }
    const start = await page.request.post(`${API_BASE}/api/runs`, {
      data: { graph, dry_run: true, allow_live: false },
    })
    const body = await start.json()
    expect(start.ok(), JSON.stringify(body)).toBeTruthy()
    let status: Record<string, any> | null = null
    await expect.poll(async () => {
      status = await (await page.request.get(`${API_BASE}/api/runs/${body.run_id}`)).json()
      return status?.status
    }, { timeout: 15_000 }).toBe('done')
    expect(status?.node_results.source.meta).toMatchObject({
      downloads: 0, expected_items: 1432, expected_train: 232, expected_test: 1200,
    })
    for (const node of graph.nodes) {
      expect(status?.node_results[node.id].status).toBe('done')
    }
  })

  test('dry-runs the single-rubric alternative with zero embeddings or critic calls', async ({ page }) => {
    const graph = {
      nodes: [
        { id: 'source', type: 'imagenhub_source', params: { repeat: 1 } },
        { id: 'dataset', type: 'dataset', params: { full_dataset: true } },
        { id: 'judge_engine', type: 'lm_engine',
          params: { engine_kind: 'gpt', model: 'mock-image-judge', max_tokens: 128 } },
        { id: 'optimizer_engine', type: 'lm_engine',
          params: { engine_kind: 'gpt', model: 'mock-optimizer', max_tokens: 128 } },
        { id: 'train', type: 'rubric_lite_train', params: { max_steps: 3 } },
        { id: 'judge', type: 'calitree_judge', params: {} },
        { id: 'eval', type: 'calitree_eval', params: {} },
      ],
      edges: [
        { source: 'source', source_socket: 'raw_dataset', target: 'dataset', target_socket: 'raw_dataset' },
        { source: 'source', source_socket: 'raw_labels', target: 'dataset', target_socket: 'raw_labels' },
        { source: 'dataset', source_socket: 'samples', target: 'train', target_socket: 'samples' },
        { source: 'dataset', source_socket: 'labels', target: 'train', target_socket: 'labels' },
        { source: 'judge_engine', source_socket: 'engine_config', target: 'train', target_socket: 'judge_engine' },
        { source: 'optimizer_engine', source_socket: 'engine_config', target: 'train', target_socket: 'optimizer_engine' },
        { source: 'dataset', source_socket: 'samples', target: 'judge', target_socket: 'samples' },
        { source: 'train', source_socket: 'prompt_tree', target: 'judge', target_socket: 'prompt_tree' },
        { source: 'judge_engine', source_socket: 'engine_config', target: 'judge', target_socket: 'judge_engine' },
        { source: 'judge', source_socket: 'judge_result', target: 'eval', target_socket: 'judge_result' },
        { source: 'dataset', source_socket: 'labels', target: 'eval', target_socket: 'labels' },
        { source: 'dataset', source_socket: 'samples', target: 'eval', target_socket: 'samples' },
      ],
    }
    const start = await page.request.post(`${API_BASE}/api/runs`, {
      data: { graph, dry_run: true, allow_live: false },
    })
    const body = await start.json()
    expect(start.ok(), JSON.stringify(body)).toBeTruthy()
    let status: Record<string, any> | null = null
    await expect.poll(async () => {
      status = await (await page.request.get(`${API_BASE}/api/runs/${body.run_id}`)).json()
      return status?.status
    }, { timeout: 15_000 }).toBe('done')
    expect(status?.node_results.train.meta).toMatchObject({
      architecture: 'rubric_lite',
      estimated_calls: { embedding: 0, critic: 0, optimizer_max: 3 },
    })
    for (const node of graph.nodes) {
      expect(status?.node_results[node.id].status).toBe('done')
    }
  })
})
