# 261008 — Enforce decomposition for a fresh three-case comparison

The user requested forcing separate decision components and approved sending the same three saved image pairs to official OpenAI GPT-6 Luna, comparing broad and decomposed greedy optimization within 900 calls / 1,152,000 completion tokens.

Added opt-in decomposition compiler/checker/proposer, frozen instruction/ledger/outcome guards, separate visual supports and an evidence-only readout. Immutable repairs cannot collapse the forced program or expand the one-check broad control. Known negative evidence remains usable; unknown necessary evidence blocks readout. The compiler and audit remain label-blind.

Added paired experiment preflight/live/resume/report modes with original case identities and image hashes, deterministic arm order, code snapshots, reserved final allowances, frozen selection, durable single-attempt accounting and scoring-fidelity analysis. Historical experiments and existing optimizer behavior are preserved. No commit or push is included in this task.

New focused offline tests: 18 passed, including failure preservation, label/image isolation, structural rejection and recovery, cache invalidation, exact saved-leaf execution and zero-call replay. Full suite and live results are recorded after completion.

## Completed verification and experiment

- Full offline unit suite before live calls: 1,209 passed, 23 skipped.
- Live run: 242 calls, 240 responses, two preserved TLS failures; returned identity `gpt-6-luna`. Reported completion tokens 24,431, conservative charged tokens 26,479, input tokens 480,903. All within the approved ceiling.
- All six selections froze before final verification. Sixty final program executions used 118 checker calls (two readouts blocked by failed support evidence).
- Broad selected agreement 60.0%, two robust cases; forced selected agreement 33.3%, one robust case. All selected coverage 100%. Every forced seed/selection remained two visual supports plus one image-free readout. All forced selections retained the seed.
- Seven of nine forced proposals were structurally invalid (nonempty root activation); two others were semantically rejected. Chalk and frog seeds failed audits. The result measures these failure modes, not successful structural repair superiority. No final results retuned frozen programs.
- Exact saved-run replay reproduced all case results with zero model calls. Protocol verification confirms hashes, topology, label isolation, image-free readout, dependency acknowledgment, reserved limits and frozen selection.
- Saved reproducible analysis/report/scripts under `logs/exps/261008-forced-decomposition-v1`; documented results in `docs/experiments/calitree_forced_decomposition.md`.

## Procedural correction and preserved follow-up

Corrected root-versus-child routing guidance and ran a separate format-only follow-up using exactly the first run's prepared seeds/audits. Prior ledger usage was deducted, keeping both attempts inside the same user-approved ceiling. No old final observations entered proposal feedback; neither original nor follow-up frozen selections were retuned.

Root errors disappeared; of ten forced proposals, two failed ordering validation and eight failed semantic audits. The follow-up froze all selections at call 113, then stopped at call 124 after three consecutive TLS failures, as required. It is inconclusive for final accuracy. All six transport failures in that attempt remain recorded, including three earlier nonconsecutive failures. No restart or model substitution was performed.

Combined accounting: 366 calls, 39,866 reported completion tokens, 48,058 charged tokens, 763,685 input tokens. Both completed-original and stopped-follow-up frozen-source replays reproduce case results with zero calls. Current source enables explicit routing by default (new preflight version v2) and clarifies complete versus partial node-order lists. The ordering clarification is offline-only; no further live run used it. Latest checks: 21 focused tests and 1,212 full unit tests passed, 23 skipped.
