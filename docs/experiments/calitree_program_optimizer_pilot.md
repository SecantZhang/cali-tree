# Casewise CaliTree leaf optimization — October 6, 2026

The replacement optimizer completed twelve independent local fits. Six selected
leaves matched their reference label in all three fresh final draws and passed
semantic auditing; three remained unstable and three consistently disagreed.
Three programs changed. One repaired program achieved a successful local fit.

| Fresh comparison | Mean case agreement | Resolved coverage | Mean final-label disagreement | Atomic unstable/unknown rate |
|---|---:|---:|---:|---:|
| Seed | 55.6% (20/36 draws) | 100% | 11.1% | 33.3% |
| Selected | 63.9% (23/36 draws) | 100% | 8.3% | 25.0% |

Each arm has twelve independent cases and three repetitions per case. All twelve
reference labels were available to their own leaf optimizer. These results measure
local fitting and repeat execution, not generalization. The cases were previously
observed, including during the earlier pilot.

## Per-case results

| Instruction | Reference | Seed matches | Selected matches | Program changed | Final status |
|---|---|---:|---:|---|---|
| Transform the black DVD into a white DVD | no | 0/3 | 2/3 | yes | unstable |
| Make her close her jacket fully | yes | 0/3 | 0/3 | no | unmatched |
| Change the image into pencil drawing | partial | 2/3 | 3/3 | yes | locally fitted |
| Give the woman a helmet | yes | 3/3 | 3/3 | no | locally fitted |
| Change the background into a basketball court | yes | 2/3 | 1/3 | no | unstable |
| Move the mug to the right of the headphones | partial | 0/3 | 0/3 | no | unmatched |
| Move the book behind the flower | no | 3/3 | 3/3 | no | locally fitted |
| Stuffing the paper into the cup | no | 3/3 | 3/3 | no | locally fitted |
| Make this look like a comic book photo | no | 3/3 | 3/3 | no | locally fitted |
| Turn the image into a drawing made from chalk | partial | 1/3 | 2/3 | yes | unstable |
| Put a frog in the toilet | partial | 0/3 | 0/3 | no | unmatched |
| The small gray rubber cylinder becomes brown | yes | 3/3 | 3/3 | no | locally fitted |

Five of the six successful leaves retained their seeds. The pencil-drawing leaf
was repaired successfully. The three selected repairs revised check criteria;
their selected programs retained one fulfillment check. Search also proposed
split and remove/add transactions, but this pilot did not demonstrate a selected
larger decision graph. Atomic reasoning correctness remains unverified.

The unchanged basketball-court program varied between fresh arms. Accordingly,
the aggregate difference must not be attributed wholly to optimization. The DVD
and chalk repairs improved observed agreement but did not meet the three-of-three
success criterion. No final comparison fed another repair attempt.

## Frozen protocol and usage

- Exact twelve prior-pilot case identities and image hashes: four per class,
  twelve distinct source-pixel groups. Every case is fitted independently.
- GPT-6 Luna for all stages, temperature zero, reasoning `none`; every returned
  model identity was `gpt-6-luna`. No replacement model was used.
- Two search rounds, beam width two, at most two compound transactions per parent;
  four total checks per program. Each candidate receives one screening draw;
  matching audited candidates receive three fresh confirmation draws.
- Final seed and selected arms receive three fresh draws each after freezing the
  leaf. Audits receive no reference label or target-conditioned rationale.
- At most 26 search calls and 24 final calls per case, with final allowance reserved
  before search. Global ceilings: 600 calls and 768,000 completion tokens.
- **203 requests:** 12 compilations, 26 audits, 16 proposals, 149 checks.
  Returned responses measured **273,103 input tokens and 16,128 completion tokens**.
  One failed proposal retains its 2,048-token reservation, bringing conservative
  completion accounting to **18,176 tokens**. No case exceeded its allowance.
- One SSL transport error occurred on a frog-case proposal. Its failed slot was
  preserved and never retried. The run did not reach three consecutive transport
  failures. There were no application parsing failures in seed compilation.
- Fourteen transactions reached candidate evaluation; one no-op transaction was
  rejected. Twenty-five audits accepted their programs and one rejected a program.
  Rejected and interrupted paths remain in the lineage and call ledger.

## Verification and reproduction

The focused suite passes **38 tests**. The complete offline unit suite passes
**1,096 tests**, with 23 live experiments skipped and 52 existing warnings.
Tests cover graph aggregation, support absence, unknown propagation, compound
repairs, binding and applicability changes, neutral intermediates, regression
rejection, label isolation, budgets, durable failures, and exact leaf reload.

The artifact verifier recomputed every final metric, checked source snapshots and
image hashes, enforced per-case budgets, checked returned identities, and reloaded
all twelve selected leaves. Each reproduced its first saved final trace from the
observation checkpoint with provider calls disabled. A completed-run resume also
reproduced identical results with zero new requests and an unchanged budget ledger.

```sh
.venv/bin/python -m logs.exps.261006-casewise-leaf-v2.verify_run
.venv/bin/python -m run.calitree_program_optimization --report \
  --output-dir logs/exps/261006-casewise-leaf-v2
```

- [Manifest and exact code hashes](../../logs/exps/261006-casewise-leaf-v2/manifest.json)
- [Saved executable leaves](../../logs/exps/261006-casewise-leaf-v2/leaves.json)
- [Complete results](../../logs/exps/261006-casewise-leaf-v2/results.json)
- [Verified accounting](../../logs/exps/261006-casewise-leaf-v2/audit.json)
- [Runtime and API guide](../calitree_program_optimizer.md)
- [Archived previous optimizer](../../logs/archives/261006-casewise-rebuild/manifest.json)

The implementation remained identical to its frozen source throughout the live
pilot. Earlier staged/uncommitted tree work was preserved; no commit or push was
performed. Parent construction, shared-rule learning and UI integration remain
out of scope.
