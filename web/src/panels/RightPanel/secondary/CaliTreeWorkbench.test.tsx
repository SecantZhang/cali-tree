import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { activeGraphStore, activeRunStore } from '../../../store/activeTab'
import { useTabsStore } from '../../../store/tabsStore'
import { CaliTreeWorkbench } from './CaliTreeWorkbench'

function node() {
  useTabsStore.getState().openBlankTab()
  activeGraphStore().getState().addNode('calitree_train', { x: 0, y: 0 })
  return activeGraphStore().getState().nodes[0]
}

describe('CaliTreeWorkbench', () => {
  it('renders hierarchy selection, metrics, progress, and image cases', () => {
    const n = node()
    activeRunStore().getState().setLastNodeResults({
      [n.id]: {
        status: 'done', error: null, meta: {}, outputs: {
          prompt_tree: {
            nodes: {
              root: {
                id: 'root', level: 1, status: 'partial', children: ['leaf'],
                covered_ids: ['case'], validation_accuracy: 0.8, prompt: 'root prompt',
                components: { criteria: ['preserve content'], priorities: [], constraints: ['JSON'] },
              },
              leaf: {
                id: 'leaf', level: 0, status: 'leaf', children: [],
                covered_ids: ['case'], validation_accuracy: 1, prompt: 'leaf prompt',
                components: { criteria: ['follow instruction'], priorities: [], constraints: [] },
              },
            },
          },
          calitree_report: {
            initial: { train: { n: 1, accuracy: 0 }, test: { n: 1, accuracy: 0 } },
            textgrad: { train: { n: 1, accuracy: 1 }, test: { n: 1, accuracy: 1 } },
            calitree: {
              train: { n: 1, accuracy: 1 },
              test: {
                n: 1, accuracy: 1, balanced_accuracy: 1,
                confusion: { yes: { yes: 1 } },
                prediction_distribution: { yes: 1 },
                per_editor: { SDEdit: { n: 1, accuracy: 1 } },
                human_agreement: { unanimous: { n: 1, accuracy: 1 } },
              },
            },
            selective: {
              test: {
                n_total: 1, n_accepted: 1, n_abstained: 0,
                coverage: 1, minimum_support: 3,
                accepted: { n: 1, accuracy: 1, balanced_accuracy: 1 },
                policy: {
                  active_editors: ['SDEdit'],
                  editor_accuracy_threshold: 0.85,
                  editor_min_support: 10,
                },
              },
            },
            timeline: [{ kind: 'partial', node_id: 'root', accuracy: 0.8 }],
            usage: { judge_calls: 3, optimizer_calls: 1 },
            optimizer_completion_token_budget: 3072,
            consensus_calibrator: {
              version: 'hierarchical-consensus-v1',
              levels: ['operation_pattern', 'pattern'],
              min_support: 4,
              selection: {
                baseline_accuracy: 0.75,
                selected_accuracy: 0.875,
                selected_levels: ['operation_pattern', 'pattern'],
                selected_min_support: 4,
              },
              rules: {
                'pattern::unanimous_yes': {
                  label: 'yes', n: 8, gain: 0.125,
                  base_accuracy: 0.75, rule_accuracy: 0.875,
                },
              },
            },
            cases: {
              case: {
                instruction: 'make it blue', source_image_path: '/source.jpg',
                edited_image_path: '/edited.jpg', editor: 'SDEdit',
                split: 'test', target_label: 'yes',
              },
            },
            predictions: {
              case: { label: 'yes', routed_node: 'root', rationale: 'correct edit' },
            },
          },
        },
      },
    })
    render(<CaliTreeWorkbench node={n} />)
    expect(screen.getByText('Cali-Tree · test').parentElement).toHaveTextContent('100.0%')
    expect(screen.getByText('Cali-Tree · test').parentElement).toHaveTextContent('balanced 100.0%')
    expect(screen.getByText('Selective · test').parentElement).toHaveTextContent('100.0%')
    expect(screen.getByLabelText('Selective calibration summary')).toHaveTextContent('coverage 100.0%')
    expect(screen.getByLabelText('Selective calibration summary')).toHaveTextContent('SDEdit')
    expect(screen.getByLabelText('Selective calibration summary')).toHaveTextContent('85%')
    expect(screen.getByRole('table', { name: 'Cali-Tree confusion matrix' })).toHaveTextContent('1')
    expect(screen.getByRole('table', { name: 'Cali-Tree per-editor accuracy' })).toHaveTextContent('SDEdit')
    expect(screen.getByLabelText('Accuracy by human agreement')).toHaveTextContent('unanimous: 100.0%')
    expect(screen.getByText('hierarchical-consensus-v1')).toBeInTheDocument()
    expect(screen.getByText(/Internal validation:/)).toHaveTextContent('75.0% → 87.5%')
    expect(screen.getByRole('table', { name: 'Consensus calibration rules' }))
      .toHaveTextContent('pattern::unanimous_yes')
    expect(screen.getByAltText('Source')).toBeInTheDocument()
    expect(screen.getByAltText('Edited')).toBeInTheDocument()
    fireEvent.click(screen.getByTitle('root'))
    expect(screen.getByText('preserve content')).toBeInTheDocument()
    expect(screen.getByText('correct edit')).toBeInTheDocument()
  })
})
