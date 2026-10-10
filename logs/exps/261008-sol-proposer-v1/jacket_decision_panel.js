      function renderDecision(stage,c,run){
        const box=$('clw-decision');clear(box);
        let decision='',output='',inputs='',next='';
        const tx=stage.type==='round'?stage.round.transactions[state.repair]:null;
        if(stage.type==='images'){
          inputs='Before/after images, instruction and rubric';
          output='Reference label: '+label(c.reference)+' (yes)';
          decision='The reference is a fitting target, not a fact supplied to the judge.';
          next='Inspect the saved starting checks.';
        }else if(stage.type==='seed'){
          inputs='Instruction and rubric; reference withheld during compilation';
          output='Two evidence questions + one fulfillment decision';
          decision='Starting screening: Unsatisfied (no) versus Satisfied (yes) reference → mismatch.';
          next='Review the meaning of the checks, then generate repair feedback.';
        }else if(stage.type==='audit'){
          inputs='Instruction, rubric and programme; no images, reference label or optimization feedback';
          output=c.audit.accepted?'Meaning approved by Luna reviewer':'Meaning rejected by Luna reviewer';
          decision='Approval is about preserving the instruction; it does not establish visual correctness.';
          next='Use the mismatching execution as feedback for repair search.';
        }else if(stage.type==='round'){
          inputs='Images, instruction, reference '+label(c.reference)+' (yes), prior observations and rejected-edit diagnostics';
          if(!tx){
            output='No proposed transaction saved';
            decision=stage.round.complete?'No new candidate to validate or execute in this round.':'Round did not complete before its call allowance was exhausted.';
          }else if(tx.error){
            output='Structural/request rejection: '+tx.error;
            decision='This proposal produced no new candidate execution. Existing evidence remains input evidence.';
          }else if(tx.duplicate){
            output='Previously evaluated programme proposed again';
            decision='Reuse its saved measurements; it is not a new independent trial.';
          }else if(tx.audit?.accepted===false){
            output='Structurally valid; semantic reviewer rejected';
            decision='Candidate is excluded from execution/selection. The reviewer reason appears below.';
          }else if(tx.audit?.accepted){
            output='Structurally valid; semantic reviewer approved';
            decision='Eligible for measurement. Approval alone does not mean target agreement or robustness.';
          }else{
            output='No completed semantic review recorded';
            decision='No approval or success is inferred from a missing review.';
          }
          const r=run.rounds[stage.index+1];
          next=r?'Next saved round uses '+(r.parent===stage.round.parent?'the same parent programme.':'a different saved parent programme.'):'Next: freeze the selected programme before final verification.';
        }else if(stage.type==='freeze'){
          inputs='Saved audited candidates and search measurements';
          output=run.selected===c.seed.ref?'Seed retained as fallback; no optimized nested result':'Repaired programme selected for frozen comparison';
          decision='Search stop: '+reason(run.stop)+'. Selection is now fixed; final results cannot trigger repair.';
          next='Run five fresh measurements of both seed and selected programme.';
        }else{
          inputs='Frozen programme, images and fresh execution slots; judges never receive the reference';
          output='Selected programme: '+Math.round(run.final.selected.agreement*5)+'/5 target matches; '+Math.round(run.final.selected.coverage*5)+'/5 resolved';
          decision=run.acceptance.qualified?'All gates passed: locally robust.':'Not locally robust: '+run.acceptance.reasons.map(reason).join('; ')+'.';
          next='Experiment complete. These verification results were not used to retune the programme.';
        }
        box.append(make('h3','','Current step · labels and decisions'));
        box.append(rowTable([['Reference target',label(c.reference)+' (yes)'],['Step input',inputs],['Step output',output],['Acceptance / loop decision',decision],['Next recorded step',next]]));
        const rep=current.report;
        if(rep){
          box.append(make('h3','','Programme predictions · '+current.measureName));
          const table=make('table','table table-sm');
          const h=make('thead'),hr=make('tr');
          for(const v of ['Draw','Judge label','Compared with reference'])hr.append(make('th','',v));
          h.append(hr);table.append(h);const b=make('tbody');
          rep.traces.forEach((t,i)=>{
            if(state.draw>=0&&state.draw!==i)return;
            const r=make('tr');
            r.append(make('td','tabular-nums',String(i+1)),make('td','',label(t.label)+(t.label?' ('+t.label+')':'')),
              make('td','',!t.resolved?'Unresolved → does not match':t.label===c.reference?'Matches target':'Mismatch'));
            b.append(r);
          });table.append(b);box.append(table);
          box.append(make('div','text-small','These labels come from the fulfillment model, not from counting supporting passes. Readout uses saved evidence and criteria. Screening, confirmation and final draws are separate measurements.'));
        }else if(stage.type==='round'){
          box.append(make('div','text-small','Proposed questions have no prediction or confidence until executed. Use “Saved measurement” to distinguish parent evidence from a candidate execution.'));
        }
      }
