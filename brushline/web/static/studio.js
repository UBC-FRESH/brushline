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
  $("#summary").textContent=`${summary.title} · observed · ${summary.tree_count} trees${summary.voltage_kv?` · ${summary.voltage_kv} kV`:""} · no treatment plan`;
 }
 drawMap();drawPareto();drawTimeline();
 await selectBlock(state.blocks[0]?.block_id);
}

function drawMap(){
 const svg=$("#map");svg.innerHTML="";
 const power=state.blocks.find(b=>b.geometry?.lines?.length);
 if(power){
  const lines=power.geometry.lines.filter(p=>p.length>1);
  const all=lines.flat();
  const xs=all.map(p=>p[0]),ys=all.map(p=>p[1]);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  const scale=Math.min(700/Math.max(1,maxX-minX),190/Math.max(1,maxY-minY));
  const ox=50+(700-(maxX-minX)*scale)/2,oy=30+(190-(maxY-minY)*scale)/2;
  const map=(p)=>[ox+(p[0]-minX)*scale,oy+(maxY-p[1])*scale];
  const g=document.createElementNS("http://www.w3.org/2000/svg","g");
  g.setAttribute("class","powerline-map");g.onclick=()=>selectBlock(power.block_id);
  lines.forEach(points=>{
   const d=points.map((p,i)=>`${i?"L":"M"}${map(p)[0].toFixed(1)} ${map(p)[1].toFixed(1)}`).join(" ");
   const casing=document.createElementNS("http://www.w3.org/2000/svg","path");
   casing.setAttribute("d",d);casing.setAttribute("fill","none");casing.setAttribute("stroke","#6f5236");casing.setAttribute("stroke-width","10");casing.setAttribute("stroke-linecap","round");casing.setAttribute("stroke-linejoin","round");g.appendChild(casing);
   const line=document.createElementNS("http://www.w3.org/2000/svg","path");
   line.setAttribute("d",d);line.setAttribute("fill","none");line.setAttribute("stroke",power.block_id===state.selected?"#e7ad4a":"#c98b3c");line.setAttribute("stroke-width","4");line.setAttribute("stroke-dasharray","8 5");line.setAttribute("stroke-linecap","round");g.appendChild(line);
  });
  (power.towers||[]).forEach(t=>{const c=document.createElementNS("http://www.w3.org/2000/svg","circle");const p=map([t.x_m,t.y_m]);c.setAttribute("cx",p[0]);c.setAttribute("cy",p[1]);c.setAttribute("r","5");c.setAttribute("fill","#35413d");c.setAttribute("stroke","#f2d59b");c.setAttribute("stroke-width","2");g.appendChild(c);});
  const label=document.createElementNS("http://www.w3.org/2000/svg","text");label.setAttribute("x","50");label.setAttribute("y","245");label.setAttribute("class","powerline-label");label.textContent=`${[...new Set(power.line_names.filter(Boolean).map(n=>n.replace(/\s*500KV$/i,"").trim()))].join(" / ")} · ${power.voltage_kv} kV`;g.appendChild(label);
  svg.appendChild(g);return;
 }
 state.blocks.forEach((b,i)=>{const r=document.createElementNS("http://www.w3.org/2000/svg","rect");r.setAttribute("x",60+(i%3)*225);r.setAttribute("y",50+Math.floor(i/3)*95);r.setAttribute("width",100);r.setAttribute("height",55);r.setAttribute("rx",8);r.setAttribute("class","segment"+(b.block_id===state.selected?" selected":""));r.onclick=()=>selectBlock(b.block_id);svg.appendChild(r);const t=document.createElementNS("http://www.w3.org/2000/svg","text");t.setAttribute("x",70+(i%3)*225);t.setAttribute("y",82+Math.floor(i/3)*95);t.setAttribute("pointer-events","none");t.textContent=b.block_id;svg.appendChild(t);});
}
function drawProvenance(){
 const scene=state.scene||{};const sources=scene.sources||[];const caveats=scene.caveats||[];
 const power=scene.powerline;
 const bbox=scene.location?.bbox_wgs84;
 const origin=bbox?` · WGS84 ${bbox[1].toFixed(4)}–${bbox[3].toFixed(4)} N, ${bbox[0].toFixed(4)}–${bbox[2].toFixed(4)} W`:(scene.origin_m?` · EPSG:3005 origin ${scene.origin_m[0].toFixed(0)}, ${scene.origin_m[1].toFixed(0)}`:"");
 const heading=power?`<strong>${esc(power.name)}</strong> · ${power.voltage_kv} kV · ${power.towers?.length||0} mapped towers${origin}`:"";
 const sourceText=sources.map(s=>`${esc(s.name)} (${esc(s.licence)})`).join(" · ");
 const caveatText=caveats.map(c=>esc(c)).join(" ");
 $("#provenance").innerHTML=[heading,sourceText,caveatText].filter(Boolean).join("<br>");
}

async function selectBlock(id){
 state.selected=id;drawMap();const b=state.blocks.find(x=>x.block_id===id);
 $("#map-hint").textContent=b?.block_kind==="powerline_block"?`${b.label} · ${b.voltage_kv} kV · ${b.height_m} m max canopy · ${b.cover_pct}% cover >3 m · ${b.tree_count} LiDAR clumps`:`${id} · ${b?.height_m??"?"} m · ${b?.cover_pct??"?"}% cover · ${b?.actions?.length||0} treatment action(s)`;
 $("#toggle").disabled=!b?.variant_available;
 const s=await api(`api/studio/scene/${id}?variant=${state.variant}&instance_id=${encodeURIComponent(state.instanceId)}`);state.scene=s;drawProvenance();drawScene();
}
function drawScene(){
 $("#scene-caveat").textContent=state.scene?.powerline?"Real MKRF power-line location and LiDAR terrain/canopy. Towers are schematic; conductors are approximate. Context view only; not a survey or safety certification.":"Context view only. Positions are unknown unless supplied; pre/post is model state, not a survey.";
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
