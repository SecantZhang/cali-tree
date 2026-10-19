/* Shared, dependency-free node/edge rule-tree view. Never changes a policy. */
(() => {
'use strict';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names=['No','Partial','Yes'];
const views=new Map(),bound=new WeakSet();
function nodesFor(tree){const nodes=[],edges=[];let leaf=0,maxDepth=0;
  function walk(node,id,depth){const n={id,node,depth,number:nodes.length+1};nodes.push(n);maxDepth=Math.max(depth,maxDepth);
    if(node.feature){const t=walk(node.true,id+'T',depth+1),f=walk(node.false,id+'F',depth+1);n.x=(t.x+f.x)/2;edges.push({from:n,to:t,value:true},{from:n,to:f,value:false});}
    else n.x=leaf++*194+106;
    n.y=depth*140+28;n.h=node.feature?82:53;return n;}
  walk(tree,'r',0);return {nodes,edges,width:Math.max(240,leaf*194+18),height:(maxDepth+1)*140+8};
}
function route(tree,values,maxTests=Infinity){const ids=new Set(),edges=new Set();
  function walk(node,id,tests){ids.add(id);if(!node.feature||tests>=maxTests)return;const value=values?.[node.feature];
    for(const b of value==='unknown'?[true,false]:typeof value==='boolean'?[value]:[]){edges.add(id+(b?'T':'F'));walk(node[b?'true':'false'],id+(b?'T':'F'),tests+1);}}
  walk(tree,'r',0);return {ids,edges};}
function wrap(text,width=23){const lines=[];let line='';for(const w of String(text).split(/\s+/)){if((line+' '+w).trim().length>width&&line){lines.push(line);line=w;}else line=(line+' '+w).trim();}if(line)lines.push(line);return lines.slice(0,3).map((l,i,a)=>i===2&&lines.length>3?l.slice(0,width-1)+'…':l);}
function render(tree,options={}){
  const key=options.id||'policy',layout=nodesFor(tree),selected=options.selected||'r';
  const path=options.highlightIds?{ids:new Set(options.highlightIds),edges:new Set(layout.edges.filter(e=>options.highlightIds.includes(e.from.id)&&options.highlightIds.includes(e.to.id)).map(e=>e.to.id))}:options.values?route(tree,options.values,options.maxTests??Infinity):{ids:new Set(),edges:new Set()};
  const model=views.get(key)||{scale:options.scale??1,left:null,top:0};model.layout=layout;model.options=options;model.tree=tree;views.set(key,model);
  const chosen=layout.nodes.find(n=>n.id===selected)||layout.nodes[0];
  const rows=options.rows||[];
  const members=new Map(layout.nodes.map(n=>[n.id,[]]));for(const row of rows){const p=route(tree,row.features);for(const id of p.ids)members.get(id)?.push(row.id);}
  const svg=`<svg class="rt-svg" viewBox="0 0 ${layout.width} ${layout.height}" width="${layout.width}" height="${layout.height}" role="group" aria-label="Branching rule tree, ${layout.nodes.length} nodes">
  ${layout.edges.map(e=>{const x1=e.from.x,y1=e.from.y+e.from.h,x2=e.to.x,y2=e.to.y,mid=(y1+y2)/2,on=path.edges.has(e.to.id);return `<g class="rt-edge ${on?'on':''}" data-tree-edge="${e.to.id}" data-branch="${e.value}"><path d="M${x1},${y1} C${x1},${mid} ${x2},${mid} ${x2},${y2}"/><text x="${(x1+x2)/2+(e.value?-5:5)}" y="${mid-6}" text-anchor="${e.value?'end':'start'}">${esc(options.branchLabels?.[String(e.value)]??(e.value?'True':'False'))}</text></g>`;}).join('')}
  ${layout.nodes.map(n=>{const isLeaf=!n.node.feature,leafLabel=isLeaf?(typeof n.node.prediction==='number'?names[n.node.prediction]:n.node.label||'Unresolved'):'',label=isLeaf?leafLabel:options.shortLabels?.[n.node.feature]||n.node.feature.replaceAll('_',' '),lines=wrap(label),active=path.ids.has(n.id),count=members.get(n.id).length;return `<g class="rt-node ${isLeaf?'leaf '+leafLabel.toLowerCase():'split'} ${active?'on':''} ${n.id===selected?'selected':''}" data-tree-action="select" data-tree-key="${esc(key)}" data-tree-node="${n.id}" role="button" tabindex="0" aria-label="Node ${n.number}: ${esc(label)}${rows.length?'; '+count+' examples':''}"><title>${esc(isLeaf?leafLabel:options.descriptions?.[n.node.feature]||label)}</title><rect x="${n.x-85}" y="${n.y}" width="170" height="${n.h}" rx="${isLeaf?20:10}"/><text class="rt-number" x="${n.x-72}" y="${n.y+16}">${esc(isLeaf?(options.leafCaption||'OUTPUT'):'N'+String(n.number).padStart(2,'0'))}${rows.length?' · '+count+' examples':''}</text>${lines.map((line,i)=>`<text class="rt-label" x="${n.x}" y="${n.y+(isLeaf?34:34)+i*15}" text-anchor="middle">${esc(line)}</text>`).join('')}</g>`;}).join('')}</svg>`;
  const selectedRows=members.get(chosen.id),desc=chosen.node.feature?options.descriptions?.[chosen.node.feature]||chosen.node.feature:((options.leafCaption||'Output')+' '+(typeof chosen.node.prediction==='number'?names[chosen.node.prediction]:chosen.node.label));
  return `<div class="rt-widget ${Object.values(options.values||{}).includes('unknown')?'uncertain':''}" data-tree-widget="${esc(key)}"><div class="rt-toolbar"><span>${esc(options.toolbarText||'True → left · False → right')}${Object.values(options.values||{}).includes('unknown')?' · dashed paths are admissible alternatives':''}</span><div><button data-tree-action="out" data-tree-key="${esc(key)}" aria-label="Zoom tree out">−</button><button data-tree-action="fit" data-tree-key="${esc(key)}">Fit tree</button><button data-tree-action="actual" data-tree-key="${esc(key)}">100%</button><button data-tree-action="in" data-tree-key="${esc(key)}" aria-label="Zoom tree in">+</button></div></div><div class="rt-viewport" tabindex="0" aria-label="Scrollable tree canvas"><div class="rt-canvas">${svg}</div></div><div class="rt-inspector"><strong>Selected node ${chosen.number} · ${esc(chosen.node.feature?'decision':'output')}</strong><span>${esc(desc)}</span>${chosen.node.feature&&options.values?`<span>Selected case value: <b>${esc(options.values[chosen.node.feature])}</b></span>`:''}${rows.length?`<span>Examples reaching this node: <b>${esc(selectedRows.join(', ')||'none in this fitting batch')}</b></span>`:''}<span class="rt-help">Click a node to inspect it. Scroll to explore branches; zoom keeps text readable.</span></div></div>`;
}
function mount(root){root.querySelectorAll('[data-tree-widget]').forEach(widget=>{const key=widget.dataset.treeWidget,view=views.get(key),vp=widget.querySelector('.rt-viewport'),canvas=widget.querySelector('.rt-canvas'),svg=widget.querySelector('svg');if(!view)return;
  const paint=()=>{canvas.style.width=view.layout.width*view.scale+'px';canvas.style.height=view.layout.height*view.scale+'px';svg.style.transform=`scale(${view.scale})`;};paint();vp.scrollLeft=view.left??Math.max(0,view.layout.nodes[0].x*view.scale-vp.clientWidth/2);vp.scrollTop=view.top;view.left=vp.scrollLeft;vp.addEventListener('scroll',()=>{view.left=vp.scrollLeft;view.top=vp.scrollTop;},{passive:true});
});}
function bind(root,onSelect){if(bound.has(root))return;bound.add(root);
  function act(e){const target=e.target.closest('[data-tree-action]');if(!target)return;if(e.type==='keydown'&&!['Enter',' '].includes(e.key))return;if(e.type==='keydown')e.preventDefault();const view=views.get(target.dataset.treeKey);if(!view)return;
    if(target.dataset.treeAction==='select'){onSelect(target.dataset.treeKey,target.dataset.treeNode);return;}
    const widget=target.closest('[data-tree-widget]'),vp=widget.querySelector('.rt-viewport');let scale=view.scale;
    if(target.dataset.treeAction==='in')scale*=1.25;if(target.dataset.treeAction==='out')scale/=1.25;if(target.dataset.treeAction==='actual')scale=1;if(target.dataset.treeAction==='fit')scale=Math.min(1,Math.max(.3,(vp.clientWidth-16)/view.layout.width));
    view.scale=Math.min(1.7,Math.max(.3,scale));view.left=null;view.top=0;mount(widget.parentElement);
  }
  root.addEventListener('click',act);root.addEventListener('keydown',act);
}
window.CaliTreeRuleTree=Object.freeze({render,mount,bind,nodesFor,route});
})();
