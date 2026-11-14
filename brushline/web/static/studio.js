const state={plan:null,pareto:null,timeline:[],blocks:[],selected:null,variant:"pre",walking:false,heading:0,position:0,time:0,skin:"operations-planner"};
const $=s=>document.querySelector(s);
const api=async p=>{const r=await fetch(p);if(!r.ok)throw new Error(await r.text());return r.json()};
const esc=s=>String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
async function boot(){
 const [summary,plan,pareto,timeline,blocks,skins]=await Promise.all([api("/api/studio/summary"),api("/api/studio/plan/current"),api("/api/studio/pareto"),api("/api/studio/timeline"),api("/api/studio/blocks"),api("/api/studio/skins")]);
 state.plan=plan;state.pareto=pareto;state.timeline=timeline.events||[];state.blocks=blocks.blocks||[];
 $("#summary").textContent=`${summary.run_id} · ${summary.plan_id} · ${summary.currency} ${summary.total_cost}`;
 $("#skin").innerHTML=skins.skins.map(s=>`<option value="${s.id}">${s.id}${s.read_only?" (read-only)":""}</option>`).join("");
 drawMap();drawPareto();drawTimeline();selectBlock(state.blocks[0]?.block_id);animate();
}
function drawMap(){
 const svg=$("#map");svg.innerHTML="";
 state.blocks.forEach((b,i)=>{const r=document.createElementNS("http://www.w3.org/2000/svg","rect");r.setAttribute("x",60+i*125);r.setAttribute("y",80+(i%2)*45);r.setAttribute("width",100);r.setAttribute("height",55);r.setAttribute("rx",8);r.setAttribute("class","segment"+(b.block_id===state.selected?" selected":""));r.onclick=()=>selectBlock(b.block_id);svg.appendChild(r);const t=document.createElementNS("http://www.w3.org/2000/svg","text");t.setAttribute("x",70+i*125);t.setAttribute("y",112+(i%2)*45);t.textContent=b.block_id;svg.appendChild(t);});
}
async function selectBlock(id){
 state.selected=id;drawMap();const b=state.blocks.find(x=>x.block_id===id);$("#map-hint").textContent=`${id} · ${b?.height_m??"?"} m · ${b?.cover_pct??"?"}% cover · ${b?.actions?.length||0} treatment action(s)`;
 $("#toggle").disabled=!b?.variant_available;
 const s=await api(`/api/studio/scene/${id}?variant=${state.variant}`);state.scene=s;drawScene();
}
function drawScene(){
 const c=$("#scene"),ctx=c.getContext("2d");ctx.fillStyle="#dfe9df";ctx.fillRect(0,0,c.width,c.height);
 ctx.strokeStyle="#9ab39e";for(let i=0;i<12;i++){ctx.beginPath();ctx.moveTo(0,300-i*18);ctx.lineTo(c.width,300-i*18);ctx.stroke();}
 const h=Math.min(180,(state.scene?.vegetation?.height_m||2)*30);ctx.fillStyle=state.variant==="post"?"#b77d4d":"#3e7a4f";ctx.fillRect(360,300-h,80,h);ctx.fillStyle="#22422d";ctx.font="14px system-ui";ctx.fillText(`${state.variant.toUpperCase()} · ${state.scene?.vegetation?.height_m??"?"} m · ${state.scene?.vegetation?.cover_pct??"?"}% cover`,20,30);
 ctx.fillStyle="#59675c";ctx.font="12px system-ui";ctx.fillText("POV: W/A/S/D move · mouse/drag look · V pre/post · Esc exit",20,52);
 $("#walk-hud").hidden=!state.walking;if(state.walking)$("#walk-hud").textContent=`${state.selected} · ${state.variant} · heading ${Math.round(state.heading)}° · position ${Math.round(state.position)}m · context view`;
 $("#variant").textContent=state.variant;
}
async function toggleVariant(){const b=state.blocks.find(x=>x.block_id===state.selected);if(!b?.variant_available)return;state.variant=state.variant==="pre"?"post":"pre";const s=await api(`/api/studio/scene/${state.selected}?variant=${state.variant}`);state.scene=s;drawScene();}
function drawPareto(){
 const members=state.pareto?.members||[];$("#pareto").innerHTML=`<table><tr><th>Plan</th><th>Cost</th><th>Risk</th></tr>${members.map(m=>`<tr><td>${esc(m.plan_id)}</td><td>${m.objective.present_cost}</td><td>${m.objective.service_risk}</td></tr>`).join("")}</table>`;
}
function drawTimeline(){
 $("#timeline").innerHTML=`<table><tr><th>Event</th><th>Resource</th><th>Segment</th><th>Start</th></tr>${state.timeline.slice(0,12).map(e=>`<tr><td>${esc(e.event_type)}</td><td>${esc(e.resource_id)}</td><td>${esc(e.segment_id)}</td><td>${esc(e.start_utc)}</td></tr>`).join("")}</table>`;
}
function animate(){if(state.walking){state.position+=0.15;if(state.position>120)state.position=0;const h=Math.min(180,(state.scene?.vegetation?.height_m||2)*30);const ctx=$("#scene").getContext("2d");ctx.fillStyle="#dfe9df";ctx.fillRect(0,0,800,420);ctx.fillStyle="#3e7a4f";ctx.fillRect(360,300-h,80,h);drawScene();}requestAnimationFrame(animate)}
$("#walk").onclick=()=>{state.walking=!state.walking;if(!state.walking){state.position=0;state.heading=0}$("#walk").textContent=state.walking?"Exit walkthrough":"Walk this block";drawScene()};
$("#toggle").onclick=toggleVariant;$("#play").onclick=()=>{state.walking=true;drawScene()};
document.addEventListener("keydown",e=>{if(e.key==="Escape"){state.walking=false;$("#walk").textContent="Walk this block";drawScene()}if(e.key.toLowerCase()==="v")toggleVariant();if(state.walking&&["w","a","s","d"].includes(e.key.toLowerCase()))state.position+=e.key.toLowerCase()==="w"?1:-1});
$("#skin").onchange=e=>{state.skin=e.target.value;document.body.dataset.skin=state.skin};
boot().catch(e=>$("#summary").textContent=`error: ${e.message}`);
