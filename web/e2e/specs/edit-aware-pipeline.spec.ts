import { expect, test } from '@playwright/test'
import { waitForPaletteLoaded } from '../helpers'

const API_BASE = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8611'

test.describe('edit-aware pipeline', () => {
  test('registers the new nodes and completes a dry-run decomposition path', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)
    for (const label of [
      'edit_decomposition', 'area_rubric', 'area_judge', 'area_aggregation',
      'unit_labels', 'edit_aware_calibration',
    ]) {
      await expect(page.locator('.node-palette-item', { hasText: label })).toBeVisible()
    }

    const graph = {
      nodes: [
        { id: 'source', type: 'peanut_source', params: {} },
        { id: 'dataset', type: 'dataset', params: { sampling_ratio: 1 } },
        { id: 'decompose', type: 'edit_decomposition', params: {} },
        { id: 'engine', type: 'lm_engine', params: { engine_kind: 'gemini' } },
        { id: 'rubric', type: 'area_rubric', params: { rubric: 'transition_smoothness' } },
        { id: 'area_judge', type: 'area_judge', params: {} },
        { id: 'aggregate', type: 'area_aggregation', params: {} },
        { id: 'eval', type: 'eval', params: {} },
      ],
      edges: [
        { source: 'source', source_socket: 'raw_dataset', target: 'dataset', target_socket: 'raw_dataset' },
        { source: 'dataset', source_socket: 'samples', target: 'decompose', target_socket: 'samples' },
        { source: 'dataset', source_socket: 'samples', target: 'area_judge', target_socket: 'samples' },
        { source: 'decompose', source_socket: 'evidence_bundle', target: 'area_judge', target_socket: 'evidence_bundle' },
        { source: 'engine', source_socket: 'engine_config', target: 'area_judge', target_socket: 'engine_config' },
        { source: 'rubric', source_socket: 'area_rubric_spec', target: 'area_judge', target_socket: 'area_rubric_spec' },
        { source: 'area_judge', source_socket: 'area_judge_result', target: 'aggregate', target_socket: 'area_judge_result' },
        { source: 'aggregate', source_socket: 'judge_result', target: 'eval', target_socket: 'judge_result' },
        { source: 'dataset', source_socket: 'labels', target: 'eval', target_socket: 'labels' },
      ],
    }
    const start = await page.request.post(`${API_BASE}/api/runs`, {
      data: { graph, dry_run: true, allow_live: false },
    })
    const startBody = await start.json()
    expect(start.ok(), JSON.stringify(startBody)).toBeTruthy()
    const { run_id: runId } = startBody
    let status: Record<string, any> | null = null
    await expect.poll(async () => {
      const response = await page.request.get(`${API_BASE}/api/runs/${runId}`)
      status = await response.json()
      return status?.status
    }, { timeout: 15_000 }).toBe('done')
    for (const nodeId of graph.nodes.map((node) => node.id)) {
      expect(status?.node_results[nodeId].status).toBe('done')
    }
    expect(status?.node_results.area_judge.meta.estimated_calls.area_judge_calls).toBe(0)
    expect(status?.node_results.aggregate.outputs.decomposition_features).toEqual({})
  })
})
