# DSG score fidelity to original programs

Score fidelity to saved original seed programs on previously observed cases; no optimization or score-guided repair.

Status: completed

Original means the exact saved label-free seed program, not a human label or an optimized program.
Main comparison: dependency-aware DSG observations, read through the original rubric without image access, versus fresh original execution.

Paired exact agreement: 73.3%; paired coverage: 83.3%.
Matching case modes: 11/12; all repeats match: 3/12.

| Instruction | Graph / audit | Original labels | DSG readout labels | Exact agreement |
|---|---|---|---|---|
| transform the black DVD into a white DVD | ready / False | yes, yes, yes, partial, ? | ?, ?, yes, ?, ? | 20.0% |
| Make her close her jacket fully | ready / False | no, no, no, no, no | no, ?, no, no, no | 80.0% |
| Change the image into pencil drawing | ready / True | yes, yes, yes, yes, yes | yes, yes, partial, yes, yes | 80.0% |
| Give the woman a helmet | ready / False | yes, yes, yes, yes, yes | ?, yes, yes, yes, ? | 60.0% |
| Change the background into a basketball court | ready / False | yes, yes, yes, yes, partial | yes, yes, yes, yes, yes | 80.0% |
| Move the mug to the right of the headphones | ready / False | yes, yes, yes, yes, yes | no, yes, yes, no, partial | 40.0% |
| Move the book behind the flower | ready / False | no, no, no, no, no | no, ?, ?, no, no | 60.0% |
| Stuffing the paper into the cup | ready / True | no, no, no, no, no | no, no, no, no, no | 100.0% |
| Make this look like a comic book photo | ready / True | no, no, no, no, no | no, no, ?, no, no | 80.0% |
| Turn the image into a drawing made from chalk | ready / True | yes, yes, yes, yes, partial | yes, yes, yes, yes, yes | 80.0% |
| Put a frog in the toilet | ready / False | yes, yes, yes, yes, yes | yes, yes, yes, yes, yes | 100.0% |
| the small gray rubber cylinder becomes brown | ready / False | yes, yes, yes, yes, yes | yes, yes, yes, yes, yes | 100.0% |

Native DSG fraction and ordinal label score (no=0, partial=0.5, yes=1) are different constructs; their numerical difference is diagnostic, not a calibrated equivalence test.
The text-only rubric readout is an explicit CaliTree adaptation, not the published DSG aggregate. It receives no original prediction or reference label.
Audits are diagnostic and all structurally valid graphs execute. No score feedback changes the questions or thresholds. Global style may remain one tuple.
Negative prerequisites suppress dependent questions with score zero. Unknown prerequisites remain unresolved. Supporting tuples contribute to the native DSG fraction but do not count as completed edits in the rubric readout.
All statistics weight cases equally. Matching two unresolved labels never counts as score agreement. Reference accuracy is secondary, separate from original-score fidelity.

Error: none
