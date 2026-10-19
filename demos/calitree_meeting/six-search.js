/* Small browser implementation of M2's bounded error/node search structure.
 * Three synthetic predicates only. Source IDs support auditing, never branching. */
(() => {
'use strict';
const ORDER=['no','partial','yes'],FEATURES=['endpoint','progress','material'];
const counts=rows=>ORDER.map(label=>rows.filter(r=>r.reference===label).length);
const majority=rows=>{const c=counts(rows);return ORDER[c.indexOf(Math.max(...c))];};
function compare(a,b){for(let i=0;i<a.length;i++){if(a[i]<b[i])return -1;if(a[i]>b[i])return 1;}return 0;}
function fit(rows,{maxDepth=2,minSupport=1,shortlist=3}={}){
  const memo=new Map();let states=0;
  function solve(subset,depth){const key=subset.map(r=>r.id).sort().join(',')+'|'+depth;if(memo.has(key))return memo.get(key);states++;
    const c=counts(subset),prediction=majority(subset),leafErrors=subset.length-Math.max(...c);
    const leaf={prediction:ORDER.indexOf(prediction)};
    let best={tree:leaf,errors:leafErrors,nodes:1};
    const candidates=FEATURES.map((feature,i)=>{const t=subset.filter(r=>r.facts[feature]),f=subset.filter(r=>!r.facts[feature]),tc=counts(t),fc=counts(f),valid=Math.min(t.length,f.length)>=minSupport;
      const immediateErrors=t.length-(Math.max(...tc)||0)+f.length-(Math.max(...fc)||0);
      const impurityRank=valid?-(tc.reduce((s,n)=>s+n*n,0)/t.length+fc.reduce((s,n)=>s+n*n,0)/f.length):0;
      return {feature,trueIds:t.map(r=>r.id),falseIds:f.map(r=>r.id),trueCounts:tc,falseCounts:fc,immediateErrors,valid,reason:!t.length||!f.length?'constant in this node':!valid?'below minimum source support':'eligible',rank:[immediateErrors,impurityRank,Math.abs(t.length-f.length),i],t,f};});
    const stop=leafErrors===0?'pure labels':depth===0?'depth budget reached':subset.length<2*minSupport?'not enough sources for two children':null;
    if(!stop){for(const p of candidates.filter(p=>p.valid).sort((a,b)=>compare(a.rank,b.rank)).slice(0,shortlist)){
      const a=solve(p.t,depth-1),b=solve(p.f,depth-1),proposal={tree:{feature:p.feature,true:a.tree,false:b.tree},errors:a.errors+b.errors,nodes:1+a.nodes+b.nodes};
      p.subtreeErrors=proposal.errors;p.subtreeNodes=proposal.nodes;
      if(compare([proposal.errors,proposal.nodes],[best.errors,best.nodes])<0)best=proposal;
      if(best.errors===0)break;
    }}
    const result={...best,ids:subset.map(r=>r.id),counts:c,leafErrors,remainingDepth:depth,stop:stop||(!best.tree.feature?'no improving legal split':null),candidates:candidates.map(({t,f,...p})=>p)};
    memo.set(key,result);return result;
  }
  const answer=solve(rows,maxDepth),decisions=[];
  function visit(node,subset,id,depth){if(!node.feature)return;const audit=solve(subset,depth);decisions.push({id,feature:node.feature,audit});visit(node.true,subset.filter(r=>r.facts[node.feature]),id+'T',depth-1);visit(node.false,subset.filter(r=>!r.facts[node.feature]),id+'F',depth-1);}
  visit(answer.tree,rows,'r',maxDepth);
  return {tree:answer.tree,errors:answer.errors,nodes:answer.nodes,states,decisions,root:answer,options:{maxDepth,minSupport,shortlist}};
}
function predict(tree,facts){let node=tree;while(node.feature)node=node[facts[node.feature]?'true':'false'];return ORDER[node.prediction];}
function partialTree(report,rows,steps){const enabled=new Set(report.decisions.slice(0,steps).map(d=>d.id));
  function walk(node,subset,id){if(!node.feature||!enabled.has(id))return {prediction:ORDER.indexOf(majority(subset))};return {feature:node.feature,true:walk(node.true,subset.filter(r=>r.facts[node.feature]),id+'T'),false:walk(node.false,subset.filter(r=>!r.facts[node.feature]),id+'F')};}
  return walk(report.tree,rows,'r');
}
function region(tree,rows,id){let node=tree,subset=rows;for(const branch of id.slice(1)){if(!node.feature)break;const yes=branch==='T';subset=subset.filter(r=>Boolean(r.facts[node.feature])===yes);node=node[yes?'true':'false'];}return subset;}
window.CaliTreeSixSearch=Object.freeze({fit,predict,partialTree,region,counts,majority});
})();
