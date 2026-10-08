# DSG score fidelity to original programs

Score fidelity to saved original seed programs on previously observed cases; no optimization or score-guided repair.

Status: running

Original means the exact saved label-free seed program, not a human label or an optimized program.
Main comparison: dependency-aware DSG observations, read through the original rubric without image access, versus fresh original execution.

Paired exact agreement: n/a; paired coverage: n/a.
Matching case modes: 0/0; all repeats match: 0/0.

| Instruction | Graph / audit | Original labels | DSG readout labels | Exact agreement |
|---|---|---|---|---|
| transform the black DVD into a white DVD | ready / False | yes, yes, yes | ?, ?, yes | n/a |
| Make her close her jacket fully | ready / False |  |  | n/a |
| Change the image into pencil drawing | ready / True |  |  | n/a |
| Give the woman a helmet | ready / False |  |  | n/a |
| Change the background into a basketball court | ready / False |  |  | n/a |
| Move the mug to the right of the headphones | ready / False |  |  | n/a |
| Move the book behind the flower | unresolved / None |  |  | n/a |
| Stuffing the paper into the cup | unresolved / None |  |  | n/a |
| Make this look like a comic book photo | ready / True |  |  | n/a |
| Turn the image into a drawing made from chalk | ready / True |  |  | n/a |
| Put a frog in the toilet | ready / False |  |  | n/a |
| the small gray rubber cylinder becomes brown | ready / False |  |  | n/a |

Native DSG fraction and ordinal label score (no=0, partial=0.5, yes=1) are different constructs; their numerical difference is diagnostic, not a calibrated equivalence test.
The text-only rubric readout is an explicit CaliTree adaptation, not the published DSG aggregate. It receives no original prediction or reference label.
Audits are diagnostic and all structurally valid graphs execute. No score feedback changes the questions or thresholds. Global style may remain one tuple.
Negative prerequisites suppress dependent questions with score zero. Unknown prerequisites remain unresolved. Supporting tuples contribute to the native DSG fraction but do not count as completed edits in the rubric readout.
All statistics weight cases equally. Matching two unresolved labels never counts as score agreement. Reference accuracy is secondary, separate from original-score fidelity.

Error: none
