# Approved contrastive-rubric pilot: completed and not promoted

The frozen 24-case training diagnostic does not improve paired accuracy. Keep the existing visual/semantic policy. Its broad development result remains **225/276 (81.5%)** with optional cached expert evidence; the strict over-85% goal requires **235/276** and is still unmet.

## Paired result

Every arm retains all 24 slots in its denominator. Rejected certificates and provider failures count as incorrect.

| Arm | Correct | Accuracy | Accepted responses | Gains / losses versus fresh regular |
|---|---:|---:|---:|---:|
| Fresh regular Luna | 15/24 | 62.5% | 24/24 | — |
| Semantic contrastive Luna | 14/24 | 58.3% | 21/24 | 2 / 3 |
| Semantic contrastive Sol | 13/24 | 54.2% | 23/24 | 3 / 5 |

These deliberately selected original training queries contain eight examples per reference class, including nine cached errors and fifteen cached-correct controls. This is a diagnostic, not an estimate for the 276-case development population or unseen data. The fresh regular judge also scores 15/24, but its individual predictions differ from the cached baseline.

The semantic prompts improve No recall (7/8 versus 5/8), while reducing Partial and Yes accuracy. Luna accepts 2/8 Partial and 5/8 Yes; Sol scores 3/8 Partial and 3/8 Yes. Fresh regular scores 4/8 Partial and 6/8 Yes. On the nine cached errors the three fresh arms score 2, 3 and 4 correct; on the fifteen controls they score 13, 11 and 9. More correct error cases do not compensate for lost controls.

## Certificate and transport failures

Three Luna responses fail the frozen certificate validator:

- **N009** and **N017** return the correct raw label Partial but select the criterion `successful_endpoint`, which belongs to Yes. These are internal certificate inconsistencies.
- **N013** returns Yes while declaring material unrequested changes. The reference is Partial; rejection prevents accepting this inconsistent success claim.

Counting the two correct raw Partial labels would give Luna 16/24. This is an explicitly post-hoc raw-label diagnostic, not the accepted pipeline result; no certificate was repaired and no acceptance rule changed. It still provides little evidence for replacing the existing judge.

One Sol request, **N009**, has a retained TLS `SSLV3_ALERT_BAD_RECORD_MAC` failure. Its single attempt remains failed; no retry or imputed label is used. The other 23 Sol certificates are accepted. Sol's losses therefore cannot be explained solely by certificate formatting or transport. Its surviving predictions also under-credit Partial/Yes edits.

## A concrete rubric mismatch

Three of Sol's five losses versus fresh regular—N003, N082 and N120—share the same certificate pattern: intended/authorized target, achieved endpoint, and `material_unrequested` collateral, producing Partial against a human Yes. The model describes respectively changed clothing during a body-size transformation, changes to a second shoe, and a missing utensil after moving a potato onto a cutting board. These are the model's descriptions, not independently verified physical facts.

This local pattern suggests that the automatic collateral cap can disagree with the human grading objective even when the requested endpoint is recognized. It is more specific than saying the stronger model cannot extract evidence. A future rubric should expose task fulfillment and preservation separately, then learn or explicitly define which preservation violations affect the task grade. It should not silently treat every material-looking collateral change as an automatic downgrade. This is a diagnostic hypothesis; the frozen pilot's validation, grades and no-fitting protocol remain unchanged, and dropping the cap is not an evaluated improvement.

The old 915-case cache also rules out a blanket removal of the material-collateral cap. An explicit counterfactual changes 33 Yes warrants: five originals (four human Partial, one Yes), thirteen primary cases (one No, ten Partial, two Yes), and fifteen matched outputs (two No, eleven Partial, two Yes). Collateral uncertainty stays blocked, and all other same-requirement warrants remain required. These counts concern logical readiness, not measured end-to-end accuracy. The original evidence and current decisions are unchanged. See [the counterfactual audit](../logs/exps/261023-collateral-cap-context-v92-r2/results.json). Both automatic capping and automatic cap removal therefore need more context; neither is a justified global replacement.

## Authorization, bounds and independent audit

The human approved the 72-request / 344,064-completion-token budget and explicitly approved uploading the prepared 94 unique AURORA images, edit instructions, compiled rubric/checks and labeled calibration contrasts to `https://api.openai.com/v1`. The earlier automatic review rejection is resolved. The unchanged frozen collector then completed all 72 attempts.

- Input tokens recorded: **221,158**.
- Known completion tokens: **20,220**.
- Completion usage including the failed Sol slot's full 8,192-token reservation: **28,412**, below the 344,064-token cap.
- Estimated recorded Standard-price usage: **$0.30685**. Including the failed output reservation: **$0.38877**, plus any unrecorded failed-request input charges. These are accounting estimates, not an invoice; cache discounts are not assumed.

There were no transport retries, certificate repairs, fitting, compiler/observer calls or reserved-source access in this experiment. Models and profiles, query/contrast source exclusions, request identities and hashes, response counts and budget accounting pass the independent completion auditor.

Authoritative evidence:

- [Completion audit](../logs/exps/261023-contrastive-v88-complete-audit-r1/verification.json), with `passed: true`, `complete: true`.
- [Per-slot raw and accepted outcomes](../logs/exps/261023-contrastive-v88-complete-audit-r1/slots.json).
- [Scored rows](../logs/exps/261023-contrastive-v88-complete-audit-r1/rows.json).
- [Frozen jobs, responses and ledger](../logs/exps/261023-contrastive-judge-v75-pilot-r2/).
- [Budget authorization](../logs/exps/261023-contrastive-judge-v75-pilot-r2/authorization.json) and [payload/destination authorization](../logs/exps/261023-contrastive-judge-v75-pilot-r2/upload_authorization.json).

## Implication

Do not promote this contrastive prompt or automatically substitute its Sol-medium certificate for the existing generic Sol-high expert contract. The results expose both certificate consistency failures and substantive grading losses. A semantic rubric needs better endpoint calibration and evidence reliability; longer structured prompts and a stronger judge alone have not supplied the required accuracy gain.

Further fitting experiments must use the pre-existing cached development inputs, not these newly collected responses under the pilot's no-fitting protocol. No additional paid collection is authorized by this completed pilot.
