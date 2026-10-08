# 261008 — Continue unattempted final verification after explicit user request

The user explicitly requested “continue” after the reported transport stop. Resume the same frozen comparison without reopening search or replacing failed observations, under the previously approved 900-call / 1,152,000-completion-token ceiling.

Added `run/calitree_resume_frozen.py`: copy the full stopped ledger and its immutable assets to a separate output, record authorization, and release only the transport-stop latch. Inherited charges, attempted slots, scope counts and failures remain. Execute the exact saved runtime in a temporary checkout; private credentials are read at their original location. Provider rejections and changed source accounting are rejected. An existing continuation that stops again is never automatically released.

The source retained 124 calls and 21,579 charged tokens; the original completed attempt used 242 calls and 26,479 charged tokens. The continuation therefore has 534 calls and 1,103,942 charged tokens remaining under the same approved ceiling. Search is fully frozen; only unattempted final slots contact the provider.

Offline coverage includes inherited accounting, retained failed slots, unattempted-only calls, frozen/source hash changes, rejection refusal, and no automatic second release. Live completion and final verification are recorded after the run.

## Completion

- Finished all remaining final verification with 108 new calls, no new transport failures, 6,704 completion tokens and 170,971 input tokens. The continued ledger contains the inherited 124 plus 108 new calls, totaling 232 for that experiment.
- Cumulative approved-work usage: 474 calls, 46,570 returned completion tokens, 54,762 conservative charged tokens, 934,656 input tokens. The stopped parent was not counted twice. All eight historical failed slots remain preserved.
- Continued follow-up selected agreement: broad 7/15 (46.7%), forced 4/15 (26.7%); both have one robust case. Broad coverage 86.7%, forced 100%. All three forced selections retained their seeds; no semantic repair succeeded. The completed first comparison remains separately documented.
- Verified unchanged source/frozen assets, attempted-job history, no accounting rollback, only unattempted final check calls, no new search, label/image isolation and full saved-result replay with zero calls.
- Full offline suite: 1,218 passed, 23 skipped. Focused suites: 27 passed. Git whitespace check passed. No commit or push.
- Results, component traces and replay scripts: `logs/exps/261008-forced-decomposition-resumed-v1/`; full narrative report: `docs/experiments/calitree_forced_decomposition.md`.
