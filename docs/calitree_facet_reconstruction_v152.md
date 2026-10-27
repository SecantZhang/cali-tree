# Semantic rubric reconstruction: development results and training diagnostic

V112 remains selected. Its **82.2% ordinary accuracy and 67.9% balanced accuracy**
come from 276 predictions across five source-held development folds, not from
training accuracy. All outputs sharing a held source are excluded from that
fold's fitting. Repeated use of these folds for research means they are not an
untouched final validation. The protected 99 fitting examples and 144 local
slots remain separate training constraints; their 100% retention is not a
generalization result.

The active target of over 80% balanced accuracy has **not** been achieved.

## Two executable semantic gates, v149

The reconstruction separates meaningful fulfillment from complete fulfillment.
The completion gate is fitted only on human Partial/Yes cases. The resulting
No/Partial/Yes masses are `1-p`, `p*(1-c)`, `p*c`. Named predicates and exact
conjunctions from the existing shallow semantic model can be shared between
the gates. Sparse coefficients, fitting-only thresholds, protected-example
vetoes and prior rule priority make the policy portable and inspectable.

Twelve fixed configurations across five source folds plus one full fit produce
72 gate pairs. No raw embeddings, case/source/editor identifiers or new model
observations enter these gates.

| Policy | Correct / 276 | Ordinary accuracy | Balanced accuracy |
|---|---:|---:|---:|
| Selected V112 | 227 | 82.2% | 67.9% |
| Primary merged predicates, cap32, C1 | 220 | 79.7% | 66.7% |
| Exploratory best, concepts cap96, C1 | 221 | 80.1% | 68.1% |

Every configuration retains all 99 originals, all 144 local slots and upstream
coverage 273/276. The independent audit re-induced all 72 gate pairs and checked
65,880 portable scalar predictions. None is promoted.

Artifacts: `logs/exps/261025-conditional-rubric-v149-r1` and
`logs/exps/261025-conditional-audit-v149-r1`.

## Reconstructed visual facets, v150–v151

Four protected fitting examples motivate separating newly realized requested
content from complete, faithful editing: duplication instead of relocation;
correct object category but wrong amount/destination; requested removal with
another entity removed; and style motifs covering only part of the scene.
The shared rubric contains no literal training objects or case identifiers.

A frozen paired diagnostic uses 24 other protected fitting examples, eight per
grade, excluding the prior twelve diagnostic sources and all 276 evaluation
sources. A pinned local Qwen3-VL-32B checkpoint sees the same two images under
the regular prompt and reconstructed facet prompt. Human labels are never
included in either prompt. The strict semantic tree is fixed before generation.

| Training-only readout | Correct / 24 | No / 8 | Partial / 8 | Yes / 8 |
|---|---:|---:|---:|---:|
| Fresh regular local control | 12 | 6 | 0 | 6 |
| Facet tree, strict | 9 | 1 | 7 | 1 |
| Facet tree with regular fallback | 10 | 2 | 7 | 1 |

All 48 attempts are terminal. There are 47 valid records; N055's facet response
contains an invalid raw control character and remains failed, without repair or
retry. The strict denominator is the full planned 24. Total emitted tokens are
6,619; the maximum observed allocation is 20,906,973,952 bytes, within the 24 GiB
soft guideline/observed peak abort. The audit replayed all 48 CPU processor
inputs, native responses, schema/grade decisions, source bindings and budgets.

The new rubric recovers Partial cases but collapses most predictions toward
Partial. Its predeclared larger-collection admission rule **fails**. These
training diagnostics are not pipeline population accuracy or a completion claim.

Artifacts: `logs/exps/261025-facet-rubric-probe-v150-r1` and
`logs/exps/261025-facet-probe-audit-v151-r1`.

## Is the decoder forcing the collapse? v152

The CPU-only audit tests every allowed value after the same earlier generated
fields: all **391 token paths are reachable** with the pinned tokenizer and
grammar bridge. This excludes a hard grammar ban; it does not establish equal
logits or correct reasoning.

Among 23 accepted facet records, `all_material_facets` is `no` in 22 and `yes`
in one. Seven records state `material_gap="none"` while asserting an explicit
categorical gap. Several written descriptions say the request is fulfilled.
Such contradictions are retained; the audit does not turn counterfactual token
paths into predictions or silently repair labels.

Artifact: `logs/exps/261025-facet-decoder-audit-v152-r1`.

## Follow-up prompt diagnostic, v153–v154

The v150 prompt described fields without displaying their literal schema/value
contract. A new frozen paired training diagnostic compares the explicit contract
with fields first versus evidence first. It reuses the same 24 fitting cases,
not an untouched validation. The model, images, bounds and v150 grade tree are
unchanged. The new field guide also forbids inventing unrequested distance or
motion-history requirements.

The run completed all48 local attempts with48 accepted records and7,808 emitted
tokens, no retries/repairs, and no API calls or uploads. The new
admission rule requires at least 23 accepted records, 18 correct, five correct
per grade and at most two literal gap contradictions. It is explicitly adapted
after the failed fitting diagnostic, not a retroactive pass of the old rule.
No larger evidence collection has been launched. The independent v154 auditor
passes all48 native/CPU processor/source/budget replays. Fields-first achieves
13/24 (No3/8,Partial7/8,Yes3/8), evidence-first10/24 (No1/8,Partial2/8,Yes7/8).
Both have zero literal gap contradictions but fail the collection screen.
Completion claims flip from19 no/4 yes/1 uncertain to6 no/17 yes/1 uncertain
with field order. Maximum observed allocation is21,230,940,740bytes.

Thirteen targeted tests pass, including failure retention/no retries and
unresolved-denominator handling. Initial test lock contention was confined to
the mock fixture and fixed by mocking its GPU lock; the live producer's lock
and frozen source are unchanged.

All work here uses zero paid API calls, zero reserved sources and no serving
changes. The selected V112 selector and weights remain unchanged.

The separate approved paid comparison and adapted outcome-primary rubric are
reported in `docs/calitree_outcome_reconstruction_v160.md`. Their training-only
metrics are not the276-case pipeline result.
