const state={instanceId:"synthetic-corridor",plan:null,pareto:null,timeline:[],blocks:[],selected:null,variant:"pre",walking:false,heading:0,position:0,time:0,skin:"operations-planner"};
const $=s=>document.querySelector(s);
const api=async p=>{const r=await fetch(p);if(!r.ok)throw new Error(await r.text());return r.json()};
const esc=s=>String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
async function boot(){
 const instances=await api("api/studio/instances");
 const select=$("#instance");select.innerHTML=instances.instances.map(i=>`<option value="${i.id}">${i.title}</option>`).join("");
 select.value=state.instanceId;
 const skins=await api("api/studio/skins");
 $("#skin").innerHTML=skins.skins.map(s=>`<option value="${s.id}">${s.id}${s.read_only?" (read-only)":""}</option>`).join("");
 await loadInstance(state.instanceId);
}
async function loadInstance(id){
 state.instanceId=id;
 const q=`?instance_id=${encodeURIComponent(id)}`;
 const [summary,blocks]=await Promise.all([api(`api/studio/summary${q}`),api(`api/studio/blocks${q}`)]);
 state.summary=summary; state.blocks=blocks.blocks||[];
 if(summary.kind==="planning"){
  const [plan,pareto,timeline]=await Promise.all([api(`api/studio/plan/current${q}`),api(`api/studio/pareto${q}`),api(`api/studio/timeline${q}`)]);
  state.plan=plan;state.pareto=pareto;state.timeline=timeline.events||[];
  $("#summary").textContent=`${summary.title} · ${summary.run_id} · ${summary.currency} ${summary.total_cost}`;
 }else{
  state.plan=null;state.pareto={members:[]};state.timeline=[];
  $("#summary").textContent=`${summary.title} · observed · ${summary.tree_count} trees · no treatment plan`;
 }
 drawMap();drawPareto();drawTimeline();
 await selectBlock(state.blocks[0]?.block_id);
}

function drawMap(){
 const svg=$("#map");svg.innerHTML="";
 state.blocks.forEach((b,i)=>{const r=document.createElementNS("http://www.w3.org/2000/svg","rect");r.setAttribute("x",60+(i%3)*225);r.setAttribute("y",50+Math.floor(i/3)*95);r.setAttribute("width",100);r.setAttribute("height",55);r.setAttribute("rx",8);r.setAttribute("class","segment"+(b.block_id===state.selected?" selected":""));r.onclick=()=>selectBlock(b.block_id);svg.appendChild(r);const t=document.createElementNS("http://www.w3.org/2000/svg","text");t.setAttribute("x",70+(i%3)*225);t.setAttribute("y",82+Math.floor(i/3)*95);t.setAttribute("pointer-events","none");t.textContent=b.block_id;svg.appendChild(t);});
}
async function selectBlock(id){
 state.selected=id;drawMap();const b=state.blocks.find(x=>x.block_id===id);$("#map-hint").textContent=`${id} · ${b?.height_m??"?"} m · ${b?.cover_pct??"?"}% cover · ${b?.actions?.length||0} treatment action(s)`;
 $("#toggle").disabled=!b?.variant_available;
 const s=await api(`api/studio/scene/${id}?variant=${state.variant}&instance_id=${encodeURIComponent(state.instanceId)}`);state.scene=s;drawScene();
}
function drawScene(){
 $("#walk-hud").hidden=!state.walking;
 if(state.walking)$("#walk-hud").textContent=`${state.selected} · ${state.variant} · context view`;
 $("#variant").textContent=state.variant;
 if(window.brushline3d) window.brushline3d.setScene(state.scene,state.variant);
 else setTimeout(()=>window.brushline3d?.setScene(state.scene,state.variant),80);
}

async function toggleVariant(){const b=state.blocks.find(x=>x.block_id===state.selected);if(!b?.variant_available)return;state.variant=state.variant==="pre"?"post":"pre";const s=await api(`api/studio/scene/${state.selected}?variant=${state.variant}&instance_id=${encodeURIComponent(state.instanceId)}`);state.scene=s;drawScene();}
function drawPareto(){
 const members=state.pareto?.members||[];$("#pareto").innerHTML=members.length?`<table><tr><th>Plan</th><th>Cost</th><th>Risk</th></tr>${members.map(m=>`<tr><td>${esc(m.plan_id)}</td><td>${m.objective.present_cost}</td><td>${m.objective.service_risk}</td></tr>`).join("")}</table>`:"<p>No Pareto archive for this observed instance.</p>";
}
function drawTimeline(){
 $("#timeline").innerHTML=state.timeline.length?`<table><tr><th>Event</th><th>Resource</th><th>Segment</th><th>Start</th></tr>${state.timeline.slice(0,12).map(e=>`<tr><td>${esc(e.event_type)}</td><td>${esc(e.resource_id)}</td><td>${esc(e.segment_id)}</td><td>${esc(e.start_utc)}</td></tr>`).join("")}</table>`:"<p>No operations timeline for this observed instance.</p>";
}
$("#walk").onclick=()=>{state.walking=!state.walking;window.brushline3d?.setWalking(state.walking);drawScene()};
$("#toggle").onclick=toggleVariant;$("#play").onclick=()=>{state.walking=true;window.brushline3d?.setWalking(true);drawScene()};
document.addEventListener("keydown",e=>{if(e.key==="Escape"){state.walking=false;window.brushline3d?.setWalking(false);drawScene()}if(e.key.toLowerCase()==="v")toggleVariant();});
window.addEventListener("brushline:exit-walk",()=>{state.walking=false;drawScene()});
$("#skin").onchange=e=>{state.skin=e.target.value;document.body.dataset.skin=state.skin};
$("#instance").onchange=e=>loadInstance(e.target.value).catch(err=>$("#summary").textContent=`error: ${err.message}`);
boot().catch(e=>$("#summary").textContent=`error: ${e.message}`);
