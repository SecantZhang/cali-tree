# CaliTree optimizer comparison

Exploratory local fitting on twelve previously observed cases. All methods receive identical label-free saved seeds. No cross-case learning or held-out generalization evaluation.

Status: completed

| Method | Seed agreement | Selected agreement | Fitted leaves | Changed programs | Structural changes | Search calls | Final calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| custom | 52.8% | 63.9% | 7/12 | 3 | 0 | 120 | 84 |
| gepa | 50.0% | 75.0% | 9/12 | 5 | 0 | 163 | 84 |
| textgrad | 47.2% | 61.1% | 5/12 | 5 | 0 | 183 | 84 |

| Instruction | Target | Custom | GEPA | TextGrad |
|---|---|---|---|---|
| transform the black DVD into a white DVD | no | 100.0% / locally_fitted | 100.0% / locally_fitted | 66.7% / unresolved |
| Make her close her jacket fully | yes | 0.0% / unmatched | 0.0% / unmatched | 0.0% / unmatched |
| Change the image into pencil drawing | partial | 100.0% / locally_fitted | 100.0% / locally_fitted | 66.7% / unresolved |
| Give the woman a helmet | yes | 100.0% / locally_fitted | 100.0% / locally_fitted | 100.0% / locally_fitted |
| Change the background into a basketball court | yes | 66.7% / unstable | 100.0% / locally_fitted | 66.7% / unstable |
| Move the mug to the right of the headphones | partial | 0.0% / unmatched | 0.0% / unmatched | 0.0% / unmatched |
| Move the book behind the flower | no | 100.0% / locally_fitted | 100.0% / locally_fitted | 100.0% / locally_fitted |
| Stuffing the paper into the cup | no | 100.0% / locally_fitted | 100.0% / locally_fitted | 100.0% / locally_fitted |
| Make this look like a comic book photo | no | 100.0% / locally_fitted | 100.0% / locally_fitted | 100.0% / locally_fitted |
| Turn the image into a drawing made from chalk | partial | 0.0% / unmatched | 100.0% / locally_fitted | 0.0% / unmatched |
| Put a frog in the toilet | partial | 0.0% / unmatched | 0.0% / unmatched | 33.3% / unstable |
| the small gray rubber cylinder becomes brown | yes | 100.0% / locally_fitted | 100.0% / locally_fitted | 100.0% / locally_fitted |

All arms use the same seed programs, checker, semantic audit, four-check cap, and 26-call search allowance per case.
Each arm has separate fresh seed and selected comparisons after all selections for that case are frozen.
The wrapper requires three matching confirmation draws and an accepted audit; final fitting status uses three additional fresh draws.
Native GEPA uses Pareto selection with a single case and no merging. TextGrad uses StringBasedFunction.backward and TGD.step on the serialized graph.
This compares constrained integrations, not unrestricted library defaults. Whole-graph updates and typed transactions are different proposal interfaces.
A structural change means outcome count, check count, or dependency edges changed. Criterion-only revisions are reported separately.
Repetitions are not independent cases. These previously observed cases cannot establish generalization or atomic semantic correctness.

Error: none
