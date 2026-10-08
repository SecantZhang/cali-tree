# Mandatory evidence decomposition on the three harder cases

Compare a one-check broad judge with mandatory decomposition on the saved basketball-background, chalk-drawing and frog-in-toilet cases. Both arms use the existing greedy robust optimizer, native TextGrad feedback, at most six structural proposals, semantic audits and the same frozen robustness thresholds.

The decomposed program has two or three focused visual support checks followed by one fulfillment readout. Support checks inspect the images independently; the readout receives only their recorded evidence. Every repair must preserve this structure and the exact original requirement ledger and outcome. The broad control remains one direct visual check. This tests a mandatory ordered evidence chain, not conditional shortcutting or cross-case generalization.

The label-free saved broad seeds are reused exactly; a label-blind compiler decomposes each independently. A shared label-blind request audits the broad and decomposed programs. Only backward/proposal requests receive the reference label. Every selection freezes before five fresh seed and five fresh selected executions per arm. Failure slots stay in the denominators and are not retried.

Approved ceiling: 900 calls and 1,152,000 completion tokens using official OpenAI GPT-6 Luna, temperature zero, reasoning `none`. Reserve 240 final calls and 245,760 completion tokens before search. Each case-arm has 109 search/confirmation and 40 final calls; preparation has two calls per case. Checker outputs cap at 1,024 tokens, other outputs at 2,048. Stop without substitution after a provider rejection or three consecutive transport failures.

The cases were previously observed and are intentionally difficult for earlier judges. Final repeat measurements do not increase the sample of independent cases beyond three. Confidence is a self-report; semantic audits and dependency acknowledgments do not establish atomic correctness. The evidence-only readout also changes information flow, so any benefit is not solely attributable to more calls or finer questions.

The first results are saved in `logs/exps/261008-forced-decomposition-v1/`, including exact programs, frozen leaves, checks, confidence, gradients, edits, audit decisions, failures, usage and code snapshots. `report.md` distinguishes reference agreement (matching the label), coverage (usable answers, including wrong ones), consistency (repeated behavior), and confidence. `scoring_fidelity.json` compares broad and decomposed scores separately from reference agreement.

## First completed run

The run completed with 242 single-attempt calls: 240 returned responses and two final-seed TLS failures. Returned model identity was `gpt-6-luna`. Reported completion usage was 24,431 tokens; conservative charged usage, including failed-slot reservations, was 26,479 tokens. Input usage was 480,903 tokens. All selections froze at call 124; 60 final executions used 118 checker calls. Unknown support evidence prevented two readout calls. The approved ceilings were preserved.

Every selected forced program had **two independent visual support checks plus one image-free readout**. Every broad program had one image-aware fulfillment check. All three forced selections retained their original seed hash. All 104 completed forced-check responses acknowledged their dependencies correctly.

| Case and reference | Broad seed → selected matches / 5 | Forced seed → selected matches / 5 | Broad / forced selected usable answers | Broad / forced robust status |
|---|---:|---:|---:|---|
| Basketball background (`yes`) | 4 → 4 | 3 → 5 | 5 / 5 | passed / passed |
| Chalk drawing (`partial`) | 0 → 5 | 0 → 0 | 5 / 5 | passed / audit failed |
| Frog in toilet (`partial`) | 0 → 0 | 0 → 0 | 5 / 5 | mismatch / audit failed |

Matching the reference is correctness at the final-label level. A usable answer is resolved, even if wrong. Robust status additionally requires semantic-audit approval, confidence, node/requirement consistency and coverage. These are three previously observed cases, not 15 independent cases per arm.

Broad selected agreement was 60.0%, with 2/3 robust cases. Forced selected agreement was 33.3%, with 1/3 robust cases. Both had 100% selected coverage. Forced selected final-label consistency was 100%, compared with broad's 93.3%; the two consistently wrong forced cases show that repeat stability is not correctness. Mean selected execution was one check / 53.7 completion tokens for broad versus three checks / 197.1 tokens for forced. This execution cost excludes compilation, proposals and feedback; full usage is saved by case scope.

The basketball forced seed→selected difference **is not an optimization gain**: the executable program was unchanged, and two seed draws failed in transport while all selected draws completed. All completed seed and selected draws matched the reference. Across the original seed formats, 13/15 same-index draw pairs matched, with two unresolved forced draws; all 13 pairs that resolved in both formats matched. Selected score fidelity was 9/15 after broad optimization changed the chalk judgments.

### Why repairs did not succeed

Of nine forced transactions, seven were rejected for assigning activation states to the root node. A root must have an empty activation list; all-state activation belongs only to children. The prompt's generic all-state wording did not reliably convey that exception. The runtime rejected those proposals and preserved their diagnostics, without automatic repair or resampling. The two structurally valid transactions failed semantic audits. Consequently no forced candidate revision was screened and selected successfully. This limits conclusions about structural optimization power.

The chalk seed checked “chalk-like medium or surface treatment” and “drawing rather than unchanged photograph.” Both supports passed in all final draws, so its readout returned `yes` with confidence at least 0.94, against the reference `partial`. The auditor had rejected the medium criterion as too restrictive for the instruction. All three proposed revisions were structurally invalid, so the rejected seed was retained and could not receive robust status. The broad optimizer instead clarified full conversion versus merely chalk-like texture or contours and returned `partial` in 5/5 final draws.

The frog seed separately checked frog presence and toilet presence. The auditor correctly identified that these contracts omit the necessary explicit **frog-in-toilet relation**. The model nevertheless returned `yes` in every final draw. Its sole structurally valid repair also failed an audit over partial-versus-absent semantics. The broad judge also returned `yes` in 5/5 draws; its accepted-audit stable mismatch is recorded as a suspected reference conflict, not proof that the annotation is wrong.

This experiment enforces multiple real checks, but does not establish that a well-formed, successfully repaired decomposition is worse than a broad judge. The next protocol should explicitly specify the root/child distinction and require relational coverage before testing repair effectiveness. The original frozen experiment was not retuned using final results.

## Format-only follow-up: inconclusive

The first run exposed an ambiguous instruction to use all-state activation. A separately frozen follow-up added an explicit exception for the root and reused the **exact original prepared seeds and audits**. It did not supply old final outcomes to feedback or change scoring semantics. The prior 242 calls / 26,479 charged tokens were deducted before allocating the remaining 658 calls / 1,125,521 tokens. Its artifacts are in `logs/exps/261008-forced-decomposition-format-v1/`.

The correction eliminated root-activation proposal errors. Ten forced transactions were proposed: two failed structural validation for incomplete node-order lists; eight passed structural validation but failed semantic audits. No forced revision replaced its seed. Audits identified incomplete relation/progress evidence and invalid complete/partial/absent/unknown composition. This shows that fixing proposal syntax alone did not produce an accepted decomposition repair.

All six selections froze at follow-up call 113. The run then stopped at call 124 after **three consecutive TLS transport failures**, preserving all failures and unattempted work. It returned 118 responses and recorded six transport errors in total. Reported completion tokens were 15,435; conservative charged tokens were 21,579; input tokens were 282,782. Final verification is incomplete, so **do not use this follow-up for an accuracy ranking**. It was not restarted after its required stop. Exact frozen-source replay reproduced the stopped result with zero model calls.

Combined usage for both attempts: **366 calls, 39,866 reported completion tokens, 48,058 conservatively charged completion tokens, 763,685 input tokens**, all within the approved 900-call / 1,152,000-completion-token ceiling. Eight transport failures remain preserved.

After the follow-up stopped, the delivered source made explicit root guidance the default for new preflights (`forced-decomposition-pilot-v2`) and added precise `node_order` instructions. The ordering clarification is offline-tested and has not been evaluated in another paid run. Existing frozen programs, selections, observations and templates in both snapshots were preserved. This procedural correction does not establish successful semantic repair. Latest offline checks: 21 focused tests; full unit suite 1,212 passed, 23 skipped.

## Authorized continuation: completed

After the user explicitly requested “continue,” the stopped follow-up was copied to `logs/exps/261008-forced-decomposition-resumed-v1/`. The exact frozen runtime and selections were restored. Only the transport-stop latch was released; all 124 inherited calls, token charges, six failed slots and per-scope counts were preserved. Search did not reopen, and no failed slot was retried.

The remaining final verification completed with **108 new calls and no new transport failures**, adding 6,704 completion tokens and 170,971 input tokens. The continued follow-up ledger contains 232 calls in total, including the inherited 124; it is not a new 232-call expense. All six case-arm comparisons now have five seed and five selected final executions. The three failures in final verification remain in their draw denominators.

| Case | Broad seed → selected matches / 5 | Forced seed → selected matches / 5 | Broad / forced selected usable / 5 | Broad / forced final status |
|---|---:|---:|---:|---|
| Basketball background | 2 → 1 | 3 → 4 | 3 / 5 | unresolved / locally robust |
| Chalk drawing | 0 → 5 | 0 → 0 | 5 / 5 | locally robust / audit failed |
| Frog in toilet | 0 → 1 | 0 → 0 | 5 / 5 | mismatched / audit failed |

Matching means agreement with the saved reference label. Usable means a resolved answer, even if wrong. The broad basketball selection retains two failed final draws, and the forced basketball seed retains its failed draw. Their missing confidence and unknown outcomes were preserved.

For this continued follow-up, broad selected agreement is **46.7% (7/15)**, with 86.7% coverage; forced selected agreement is **26.7% (4/15)**, with 100% coverage. Both methods have one locally robust case. These are three cases measured repeatedly, not fifteen independent cases per method. Different broad revisions and fresh stochastic draws make these results distinct from the first completed comparison; neither table supersedes or erases the other.

All three forced selected programs still equal their seeds. The basketball seed-to-selected difference is repeat variability plus the retained failed seed draw, not a learned improvement. The format fix removed root activation errors, but no proposed forced revision passed all audits. Chalk still scores `yes` instead of `partial`, and frog still scores `yes` instead of `partial`. Completing verification therefore does not demonstrate successful structural optimization or atomic semantic correctness.

The total approved-work accounting is now **474 calls, 46,570 reported completion tokens, 54,762 conservatively charged completion tokens, and 934,656 input tokens**. This counts the original completed run plus the continued follow-up, without adding its inherited parent ledger twice. All remain within 900 calls / 1,152,000 completion tokens. Eight historical transport failures are preserved; no new failures occurred during continuation.

Verification confirmed unchanged parent assets and failed jobs, exact frozen leaf/program hashes, no new search calls, only unattempted final checks, label/image isolation, budget preservation and zero-call replay parity. Latest offline suite: **1,218 passed, 23 skipped**; 27 focused decomposition/continuation tests passed. The continuation is a completed negative experiment, not evidence that every decomposition approach will fail.

## Reproduction and component inspection

The run's `analysis.md` and `component_analysis.json` show every selected component, its inputs, final states, confidence and audit/repair failures. `report.md`, `summary.json`, `scoring_fidelity.json` and `protocol_verification.json` provide aggregate results. Exact programs and full search histories are in `prepared/`, `frozen/` and `leaves.json`; single-attempt provider records are in `jobs/`.

```bash
PYTHONPATH=. .venv/bin/python logs/exps/261008-forced-decomposition-v1/analyze_saved_run.py
PYTHONPATH=. .venv/bin/python logs/exps/261008-forced-decomposition-v1/replay_frozen_snapshot.py
PYTHONPATH=. .venv/bin/python logs/exps/261008-forced-decomposition-format-v1/replay_frozen_snapshot.py
PYTHONPATH=. .venv/bin/python logs/exps/261008-forced-decomposition-resumed-v1/analyze_saved_run.py
PYTHONPATH=. .venv/bin/python logs/exps/261008-forced-decomposition-resumed-v1/replay_frozen_snapshot.py
```

Protocol verification checked label isolation, image-free readouts, dependency acknowledgments, frozen selection, topology, budget limits and exact saved replay. Replay reproduced the completed original, stopped follow-up and completed continuation with **zero model calls** using their frozen runtime snapshots in temporary checkouts. Direct current-code resume intentionally rejects the older configuration. Offline checks before the first live execution passed: 18 focused tests and 1,209 full unit tests, with 23 skips. Existing implementations and historical artifacts remain unchanged; these additions are uncommitted and unpushed.
