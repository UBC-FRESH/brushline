const state={instanceId:"synthetic-corridor",plan:null,pareto:null,timeline:[],blocks:[],selected:null,variant:"pre",walking:false,heading:0,position:0,time:0,skin:"operations-planner",year:2026,schedule:null,network:null};
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
 state.schedule=null;state.year=2026;state.network=null;$("#time-control").hidden=true;$("#brief-link").hidden=true;
 const q=`?instance_id=${encodeURIComponent(id)}`;
 const [summary,blocks]=await Promise.all([api(`api/studio/summary${q}`),api(`api/studio/blocks${q}`)]);
 state.summary=summary; state.blocks=blocks.blocks||[];
 const observedSchedule=state.blocks[0]?.treatment_schedule;
 if(summary.kind==="network"){
  state.network=await api(`api/studio/network${q}`);
  state.plan=null;state.pareto={members:[]};state.timeline=[];
  $("#summary").textContent=`${summary.title} · ${summary.aoi_ha} ha · ${summary.line_km} km · ${summary.feature_count} features · ${summary.scenario_count} scenarios`;
  $("#brief-link").href=`api/studio/network/brief?instance_id=${encodeURIComponent(id)}`;
  $("#brief-link").hidden=false;
 }else if(summary.kind==="planning"){
  const [plan,pareto,timeline]=await Promise.all([api(`api/studio/plan/current${q}`),api(`api/studio/pareto${q}`),api(`api/studio/timeline${q}`)]);
  state.plan=plan;state.pareto=pareto;state.timeline=timeline.events||[];
  $("#summary").textContent=`${summary.title} · ${summary.run_id} · ${summary.currency} ${summary.total_cost}`;
 }else{
  state.plan=null;state.pareto={members:[]};state.timeline=[];
  $("#summary").textContent=`${summary.title} · observed · ${summary.tree_count} trees${summary.understory_patch_count?` · ${summary.understory_patch_count} shrubs`:""}${summary.voltage_kv?` · ${summary.voltage_kv} kV`:""} · ${observedSchedule?"modelled schedule":"no treatment plan"}`;
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
  if(state.schedule?.units){
   state.schedule.units.forEach(unit=>{
    const points=unit.points||[];if(points.length<2)return;
    const d=points.map((p,i)=>`${i?"L":"M"}${map(p)[0].toFixed(1)} ${map(p)[1].toFixed(1)}`).join(" ");
    const path=document.createElementNS("http://www.w3.org/2000/svg","path");
    const planned=unit.planned?.year;const current=planned===state.year;
    path.setAttribute("d",d);path.setAttribute("fill","none");
    path.setAttribute("stroke",current?"#d9691f":state.year>planned?"#355a3e":"#b5a078");
    path.setAttribute("stroke-width",current?"8":"6");
    path.setAttribute("stroke-dasharray",current?"":"10 5");
    path.setAttribute("stroke-linecap","round");path.setAttribute("stroke-linejoin","round");
    path.style.cursor="pointer";path.setAttribute("title",`${unit.unit_id} · ${planned} · ${unit.planned?.method||"planned"}`);
    path.onclick=(event)=>{event.stopPropagation();setYear(planned);};
    g.appendChild(path);
   });
  }
  const label=document.createElementNS("http://www.w3.org/2000/svg","text");label.setAttribute("x","50");label.setAttribute("y","245");label.setAttribute("class","powerline-label");const names=[...new Set(power.line_names.filter(Boolean).map(n=>n.replace(/\s*500KV$/i,"").trim()))].join(" / ");label.textContent=`${names}${power.voltage_kv?` · ${power.voltage_kv} kV`:""}`;g.appendChild(label);
  svg.appendChild(g);return;
 }
 state.blocks.forEach((b,i)=>{const r=document.createElementNS("http://www.w3.org/2000/svg","rect");r.setAttribute("x",60+(i%3)*225);r.setAttribute("y",50+Math.floor(i/3)*95);r.setAttribute("width",100);r.setAttribute("height",55);r.setAttribute("rx",8);r.setAttribute("class","segment"+(b.block_id===state.selected?" selected":""));r.onclick=()=>selectBlock(b.block_id);svg.appendChild(r);const t=document.createElementNS("http://www.w3.org/2000/svg","text");t.setAttribute("x",70+(i%3)*225);t.setAttribute("y",82+Math.floor(i/3)*95);t.setAttribute("pointer-events","none");t.textContent=b.block_id;svg.appendChild(t);});
}
function drawProvenance(){
 const scene=state.scene||{};const sources=scene.sources||[];const caveats=scene.caveats||[];
 const power=scene.powerline;
 const bbox=scene.location?.bbox_wgs84;
 const origin=bbox?` · WGS84 ${bbox[1].toFixed(4)}–${bbox[3].toFixed(4)} N, ${bbox[0].toFixed(4)}–${bbox[2].toFixed(4)} W`:(scene.origin_m?` · EPSG:3005 origin ${scene.origin_m[0].toFixed(0)}, ${scene.origin_m[1].toFixed(0)}`:"");
 const under=scene.understory;
 const underText=under?.patch_count?`${under.patch_count} LiDAR shrub patches · ${under.corridor_patch_count} in the 70 m corridor (${under.corridor_mean_cover_pct}% mean cover)` : "";
 const heading=power?`<strong>${esc(power.name)}</strong> · ${power.voltage_kv} kV · ${power.towers?.length||0} mapped towers${origin}${underText?`<br>${underText}`:""}`:"";
 const sourceText=sources.map(s=>`${esc(s.name)} (${esc(s.licence)})`).join(" · ");
 const caveatText=caveats.map(c=>esc(c)).join(" ");
 $("#provenance").innerHTML=[heading,sourceText,caveatText].filter(Boolean).join("<br>");
}

async function selectBlock(id){
 const b=state.blocks.find(x=>x.block_id===id);
 state.selected=id;state.schedule=b?.treatment_schedule||null;
 $("#map-hint").textContent=b?.block_kind==="network_block"?`${b.label} · ${b.line_names?.length||0} mapped features · ${b.tree_count} VRI stand clumps · ${b.towers?.length||0} mapped towers` : b?.block_kind==="powerline_block"?`${b.label} · ${b.voltage_kv} kV · ${b.height_m} m max canopy · ${b.cover_pct}% cover >3 m · ${b.tree_count} tree clumps · ${b.understory_patch_count} shrubs (${b.understory_corridor_count} in corridor)`:`${id} · ${b?.height_m??"?"} m · ${b?.cover_pct??"?"}% cover · ${b?.actions?.length||0} treatment action(s)`;
 $("#toggle").disabled=!b?.variant_available;
 const s=await api(`api/studio/scene/${id}?variant=${state.variant}&instance_id=${encodeURIComponent(state.instanceId)}`);state.scene=s;state.schedule=s.treatment_schedule||state.schedule;
 configureYear();drawProvenance();drawMap();drawSchedule();drawTimeline();drawScene();
 setTimeout(()=>window.brushline3d?.setYear(state.year),80);
}

function configureYear(){
 if(state.network){
  const rows=state.network.strategic?.stateful_scenarios?.[0]?.rows||[];
  if(!rows.length){$("#time-control").hidden=true;return;}
  const min=rows[0].year,max=rows[rows.length-1].year;
  state.year=Math.max(min,Math.min(max,state.year));
  const input=$("#year");input.min=min;input.max=max;input.step=1;input.value=state.year;input.disabled=false;
  $("#time-control").hidden=false;updateNetworkYear();return;
 }
 const s=state.schedule;
 if(!s){$("#time-control").hidden=true;return;}
 const axis=s.time_axis||[s.baseline_year||2026];
 const min=axis[0],max=axis[axis.length-1];
 state.year=Math.max(min,Math.min(max,state.year));
 const input=$("#year");input.min=min;input.max=max;input.step=1;input.value=state.year;input.disabled=false;
 $("#time-control").hidden=false;updateYearLabel();
}
function updateNetworkYear(){
 if(!state.network)return;
 $("#year-label").textContent=`${state.year} modelled`;
 $("#variant").textContent="network prototype";
}
function yearText(){
 const s=state.schedule;if(!s)return "";
 return `${state.year}${state.year===s.baseline_year?" observed":" modelled"}`;
}
function updateYearLabel(){
 const s=state.schedule;if(!s)return;
 const label=yearText();
 $("#year-label").textContent=label;
 $("#variant").textContent=label;
}
function setYear(year){
 if(state.network){
  state.year=Number(year);$("#year").value=state.year;updateNetworkYear();drawSchedule();drawTimeline();
  return;
 }
 if(!state.schedule)return;
 state.year=Number(year);$("#year").value=state.year;updateYearLabel();drawSchedule();drawMap();
 window.brushline3d?.setYear(state.year);
}
function drawSchedule(){
 if(state.network){
  $("#schedule-heading").textContent="Strategic budget and treatment schedule";
  const strategic=state.network.strategic||{};
  const tactical=state.network.tactical||{};
  const portfolios=strategic.milp_scenarios||strategic.stateful_scenarios||strategic.portfolios||[];
  const scenarioRows=portfolios.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.annual_budget.toFixed(0)}</td><td>${p.five_year_cost.toFixed(0)}</td><td>${p.mean_service.toFixed(3)}</td><td>${p.mean_risk.toFixed(3)}</td><td>${p.mean_annual_hours.toFixed(0)}</td></tr>`).join("");
  const bau=strategic.stateful_bau||strategic.bau;
  const capacity=(state.network.network?.assumptions?.contractor_capacity||[]).reduce((sum,value)=>sum+value,0);
  const balanced=portfolios.find(p=>p.name.includes("60000"))||portfolios.find(p=>p.name.includes("balanced"))||portfolios[0];
  const utilization=balanced&&capacity?`${balanced.mean_annual_hours.toFixed(0)} h/yr balanced demand (${(balanced.mean_annual_hours/capacity*100).toFixed(0)}% of modelled capacity)`:"no capacity estimate";
  const selectedScenario=portfolios.find(p=>p.name.includes("60000"))||portfolios.find(p=>p.name.includes("balanced"))||portfolios[0];
  const selectedRow=selectedScenario?.rows?.find(row=>row.year===state.year);
  const annual=selectedRow?`<p class="schedule-note">${state.year} selected-year projection: ${selectedRow.actions} actions; ${selectedRow.cost.toFixed(0)} cost; ${selectedRow.hours.toFixed(0)} crew-hours; service ${selectedRow.service.toFixed(3)}; risk ${selectedRow.risk.toFixed(3)}.</p>`:"";
  const workforceRows=(state.network.workforce||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${item.reassigned_hours.toFixed(0)}</td><td>${item.resource_cost.toFixed(0)}</td><td>${item.resource_feasible}</td><td>${item.shift_feasible}</td></tr>`).join("");
  $("#schedule").innerHTML=`<p class="schedule-note">MILP budget scenarios from public line geometry and VRI-derived stand pressure. Costs, hours, access, and contractor capacity are demo assumptions. Modelled contractor capacity: ${capacity.toFixed(0)} h/yr; ${utilization}.</p><table><tr><th>Scenario</th><th>Budget/yr</th><th>5-year cost</th><th>Service</th><th>Risk</th><th>Hours/yr</th></tr>${scenarioRows}${bau?`<tr><td>BAU 5-year mowing</td><td>0</td><td>${(bau.five_year_cost||0).toFixed(0)}</td><td>${(bau.mean_service??0).toFixed(3)}</td><td>${(bau.mean_risk??0).toFixed(3)}</td><td>${(bau.mean_annual_hours||0).toFixed(0)}</td></tr>`:""}</table>${annual}<p class="schedule-note">Tactical selected actions: ${tactical.actions?.length||0}; tactical cost: ${(tactical.total_cost||0).toFixed(0)}; work orders: ${state.network.operations?.work_orders?.length||0}.</p><p class="schedule-note">Workforce scenarios</p><table><tr><th>Scenario</th><th>Reassigned h</th><th>Resource cost</th><th>Resource feasible</th><th>Shift feasible</th></tr>${workforceRows}</table><p class="schedule-note">Commercial check: owner plan ${state.network.bid?.owner_total?.toFixed(0)} · bid ${state.network.bid?.bid?.total_cost?.toFixed(0)} · delta ${state.network.bid?.comparison?.delta?.toFixed(0)} · fair range ${state.network.bid?.comparison?.fair_low?.toFixed(0)}–${state.network.bid?.comparison?.fair_high?.toFixed(0)}</p>`;
  const uncertainty=state.network.uncertainty;
  if(uncertainty){
   $("#schedule").innerHTML+=`<p class="schedule-note">Execution uncertainty around the balanced plan</p><table><tr><th>Metric</th><th>P10</th><th>P50</th><th>P90</th><th>Shortfall probability</th></tr><tr><td>5-year cost</td><td>${uncertainty.cost_band.p10.toFixed(0)}</td><td>${uncertainty.cost_band.p50.toFixed(0)}</td><td>${uncertainty.cost_band.p90.toFixed(0)}</td><td>${(uncertainty.probability_budget_exceeded*100).toFixed(1)}% budget</td></tr><tr><td>5-year crew-hours</td><td>${uncertainty.hours_band.p10.toFixed(0)}</td><td>${uncertainty.hours_band.p50.toFixed(0)}</td><td>${uncertainty.hours_band.p90.toFixed(0)}</td><td>${(uncertainty.probability_capacity_shortfall*100).toFixed(1)}% capacity</td></tr></table>`;
  }
  const adaptive=state.network["scenario-optimization"];
  if(adaptive){
   $("#schedule").innerHTML+=`<p class="schedule-note">Hindsight adaptive planning · ${adaptive.scenarios} exact scenario re-solves · not a deployable policy</p><table><tr><th>Policy</th><th>5-year cost P10–P90</th><th>Mean risk</th><th>Budget violation</th></tr><tr><td>Fixed balanced plan</td><td>${adaptive.fixed_cost_band.p10.toFixed(0)}–${adaptive.fixed_cost_band.p90.toFixed(0)}</td><td>${adaptive.fixed_risk_band.mean.toFixed(4)}</td><td>${(adaptive.fixed_budget_violation_probability*100).toFixed(1)}%</td></tr><tr><td>Scenario-optimized</td><td>${adaptive.adaptive_cost_band.p10.toFixed(0)}–${adaptive.adaptive_cost_band.p90.toFixed(0)}</td><td>${adaptive.adaptive_risk_band.mean.toFixed(4)}</td><td>0.0%</td></tr></table>`;
  }
  const rolling=state.network["rolling-policy"];
  if(rolling){
   $("#schedule").innerHTML+=`<p class="schedule-note">Rolling-horizon policy · ${rolling.lookahead_years}-year lookahead · ${rolling.episodes} annual-factor episodes · persistence forecast</p><table><tr><th>Policy</th><th>5-year cost P10–P90</th><th>Mean risk</th><th>Budget violation</th><th>Capacity violation</th></tr><tr><td>Fixed nominal</td><td>${rolling.fixed_cost_band.p10.toFixed(0)}–${rolling.fixed_cost_band.p90.toFixed(0)}</td><td>${rolling.fixed_risk_band.mean.toFixed(4)}</td><td>${(rolling.fixed_budget_violation_probability*100).toFixed(1)}%</td><td>${(rolling.fixed_capacity_violation_probability*100).toFixed(1)}%</td></tr><tr><td>Rolling policy</td><td>${rolling.rolling_cost_band.p10.toFixed(0)}–${rolling.rolling_cost_band.p90.toFixed(0)}</td><td>${rolling.rolling_risk_band.mean.toFixed(4)}</td><td>${(rolling.rolling_budget_violation_probability*100).toFixed(1)}%</td><td>${(rolling.rolling_capacity_violation_probability*100).toFixed(1)}%</td></tr></table>`;
  }
  return;
 }
 $("#schedule-heading").textContent="Corridor treatment schedule";
 const s=state.schedule;
 if(!s){$("#schedule").innerHTML="<p>No modelled treatment schedule for this block.</p>";return;}
 const rows=(s.units||[]).map(unit=>{
  const p=unit.planned||{};
  const current=p.year===state.year;
  const status=current?"this year":state.year>p.year?"modelled treated":"planned";
  return `<tr class="${current?"current":""}" title="${esc(p.driver||"")}"><td>${esc(p.year)}</td><td>${esc(unit.unit_id)}<br><small>${esc(unit.line_name||"")}</small></td><td>${esc(p.method||"")}</td><td>${unit.area_ha} ha</td><td>${unit.shrub_patch_count}</td><td>${unit.mean_cover_pct}%</td><td>${esc(p.monitor_year||"")}</td><td>${esc(p.proposed_window||"")}<br><small>${esc(status)}</small></td></tr>`;
 }).join("");
 $("#schedule").innerHTML=`<p class="schedule-note">Baseline ${s.baseline_year}: observed LiDAR. Slider is a modelled maintenance sequence; shrub response is illustrative, not field-calibrated.</p><table><tr><th>Year</th><th>Unit</th><th>Method</th><th>Area</th><th>Shrubs</th><th>Cover</th><th>Monitor</th><th>Window / status</th></tr>${rows}</table>`;
}
function drawScene(){
 $("#scene-caveat").textContent=state.network?"BC Hydro public-data network prototype: OSM line geometry, VRI stand context, and Copernicus terrain. Not an asset-owner plan or safety certification.":state.scene?.powerline?"Real MKRF power-line location, LiDAR terrain/canopy, and LiDAR-derived shrub patches. The dark green low clumps in the corridor are mapped shrub patches. Towers are schematic; conductors are approximate. Tall-tree suppression is a corridor visualization choice, not observed treatment. Context view only; not a survey or safety certification.":"Context view only. Positions are unknown unless supplied; pre/post is model state, not a survey.";
 $("#walk-hud").hidden=!state.walking;
 if(state.walking)$("#walk-hud").textContent=`${state.selected} · ${state.variant} · context view`;
 $("#variant").textContent=state.variant;
 if(window.brushline3d) window.brushline3d.setScene(state.scene,state.variant);
 else setTimeout(()=>window.brushline3d?.setScene(state.scene,state.variant),80);
 if(state.network) $("#variant").textContent="prototype";
 else if(state.schedule) $("#variant").textContent=yearText();
}

async function toggleVariant(){const b=state.blocks.find(x=>x.block_id===state.selected);if(!b?.variant_available)return;state.variant=state.variant==="pre"?"post":"pre";const s=await api(`api/studio/scene/${state.selected}?variant=${state.variant}&instance_id=${encodeURIComponent(state.instanceId)}`);state.scene=s;drawScene();}
function drawPareto(){
 if(state.network){
  $("#pareto-heading").textContent="Strategy frontier, cycles, and scaling";
  const frontier=state.network.strategic?.milp_frontier||[];
  const costs=frontier.map(item=>item.five_year_cost);
  const minCost=Math.min(...costs,0),maxCost=Math.max(...costs,1);
  const maxRisk=Math.max(...frontier.map(item=>item.mean_risk),0.01);
  const sx=(cost)=>50+(cost-minCost)/Math.max(1,maxCost-minCost)*520;
  const sy=(risk)=>20+(maxRisk-risk)/Math.max(0.01,maxRisk)*165;
  const points=frontier.map(item=>`${sx(item.five_year_cost).toFixed(1)},${sy(item.mean_risk).toFixed(1)}`).join(" ");
  const dots=frontier.map(item=>`<circle cx="${sx(item.five_year_cost).toFixed(1)}" cy="${sy(item.mean_risk).toFixed(1)}" r="5" fill="#d9691f"><title>${esc(item.name)} · ${item.five_year_cost.toFixed(0)} cost · ${item.mean_risk.toFixed(3)} risk</title></circle>`).join("");
  const chart=`<svg viewBox="0 0 620 230" role="img" aria-label="Cost versus risk frontier" style="width:100%;height:auto;background:#f4f7f2;border-radius:7px"><line x1="50" y1="185" x2="580" y2="185" stroke="#8b9a8d"/><line x1="50" y1="20" x2="50" y2="185" stroke="#8b9a8d"/><text x="50" y="205" font-size="10" fill="#59675c">lower cost → ${maxCost.toFixed(0)}</text><text x="8" y="20" font-size="10" fill="#59675c" transform="rotate(-90 8 20)">higher risk →</text><polyline points="${points}" fill="none" stroke="#d9691f" stroke-width="2" opacity=".7"/>${dots}</svg>`;
  const frontierRows=frontier.map(item=>`<tr><td>${item.annual_budget.toFixed(0)}</td><td>${item.five_year_cost.toFixed(0)}</td><td>${item.mean_service.toFixed(3)}</td><td>${item.mean_risk.toFixed(3)}</td><td>${item.mean_annual_hours.toFixed(0)}</td></tr>`).join("");
  const capacityRows=(state.network.strategic?.milp_capacity||[]).map(item=>`<tr><td>${item.name.replace("capacity-","")}</td><td>${item.five_year_cost.toFixed(0)}</td><td>${item.mean_service.toFixed(3)}</td><td>${item.mean_risk.toFixed(3)}</td></tr>`).join("");
  const cycleRows=(state.network.strategic?.stateful_cycles||[]).map(item=>`<tr><td>${esc(item.method)}</td><td>${item.cycle_years}</td><td>${item.five_year_cost.toFixed(0)}</td><td>${item.mean_annual_hours.toFixed(0)}</td><td>${item.mean_risk.toFixed(3)}</td></tr>`).join("");
  const scaleRows=(state.network.strategic?.scalability||[]).map(item=>`<tr><td>${item.segments}</td><td>${item.variables}</td><td>${item.seconds.toFixed(2)}</td><td>${item.mean_risk.toFixed(3)}</td><td>${item.status}</td></tr>`).join("");
  $("#pareto").innerHTML=`<p class="schedule-note">Budget/risk frontier: non-dominated stateful MILP outcomes. Capacity sensitivity holds the 100k/yr budget and varies crew-hours.</p>${chart}<table><tr><th>Budget/yr</th><th>5-year cost</th><th>Service</th><th>Risk</th><th>Hours/yr</th></tr>${frontierRows}</table><p class="schedule-note">Contractor capacity sensitivity</p><table><tr><th>Capacity h/yr</th><th>5-year cost</th><th>Service</th><th>Risk</th></tr>${capacityRows}</table><p class="schedule-note">Fixed-cycle tradeoff</p><table><tr><th>Method</th><th>Cycle</th><th>5-year cost</th><th>Hours/yr</th><th>Mean risk</th></tr>${cycleRows}</table><p class="schedule-note">Fresh Solutions heuristic scaling (20 iterations after greedy seed)</p><table><tr><th>Segments</th><th>Variables</th><th>Seconds</th><th>Mean risk</th><th>Status</th></tr>${scaleRows}</table>`;
  return;
 }
 $("#pareto-heading").textContent="Pareto archive";
 const members=state.pareto?.members||[];$("#pareto").innerHTML=members.length?`<table><tr><th>Plan</th><th>Cost</th><th>Risk</th></tr>${members.map(m=>`<tr><td>${esc(m.plan_id)}</td><td>${m.objective.present_cost}</td><td>${m.objective.service_risk}</td></tr>`).join("")}</table>`:"<p>No Pareto archive for this observed instance.</p>";
}
function drawTimeline(){
 if(state.network){
  $("#timeline-heading").textContent="Shift schedule";
  const shifts=(state.network.shifts?.assignments||[]).filter(item=>item.year===state.year);
  if(shifts.length){
   $("#timeline").innerHTML=`<table><tr><th>Year</th><th>Day</th><th>Crew</th><th>Machine</th><th>Unit</th><th>Method</th><th>Prod. h</th><th>Travel h</th></tr>${shifts.slice(0,24).map(item=>`<tr><td>${item.year}</td><td>${item.day}</td><td>${esc(item.crew_id)}</td><td>${esc(item.machine_id||"—")}</td><td>${esc(item.unit_id)}</td><td>${esc(item.method)}</td><td>${item.productive_hours.toFixed(1)}</td><td>${item.travel_hours.toFixed(1)}</td></tr>`).join("")}</table>`;
   return;
  }
  const orders=(state.network.operations?.work_orders||[]).filter(order=>order.year===state.year);
  $("#timeline").innerHTML=orders.length?`<table><tr><th>Year</th><th>Seq. day</th><th>Unit</th><th>Method</th><th>Crew</th><th>Cost</th></tr>${orders.slice(0,20).map(o=>`<tr><td>${o.year}</td><td>${o.day}</td><td>${esc(o.unit_id)}</td><td>${esc(o.method)}</td><td>${esc(o.crew_id)}</td><td>${o.cost.toFixed(0)}</td></tr>`).join("")}</table>`:"<p>No work orders.</p>";
  return;
 }
 $("#timeline-heading").textContent="Operations timeline";
 $("#timeline").innerHTML=state.timeline.length?`<table><tr><th>Event</th><th>Resource</th><th>Segment</th><th>Start</th></tr>${state.timeline.slice(0,12).map(e=>`<tr><td>${esc(e.event_type)}</td><td>${esc(e.resource_id)}</td><td>${esc(e.segment_id)}</td><td>${esc(e.start_utc)}</td></tr>`).join("")}</table>`:"<p>No operations timeline for this observed instance.</p>";
}
$("#walk").onclick=()=>{state.walking=!state.walking;window.brushline3d?.setWalking(state.walking);drawScene()};
$("#toggle").onclick=toggleVariant;$("#play").onclick=()=>{state.walking=true;window.brushline3d?.setWalking(true);drawScene()};
document.addEventListener("keydown",e=>{if(e.key==="Escape"){state.walking=false;window.brushline3d?.setWalking(false);drawScene()}if(e.key.toLowerCase()==="v")toggleVariant();});
window.addEventListener("brushline:exit-walk",()=>{state.walking=false;drawScene()});
$("#year").addEventListener("input",e=>setYear(Number(e.target.value)));
$("#skin").onchange=e=>{state.skin=e.target.value;document.body.dataset.skin=state.skin};
$("#instance").onchange=e=>loadInstance(e.target.value).catch(err=>$("#summary").textContent=`error: ${err.message}`);
boot().catch(e=>$("#summary").textContent=`error: ${e.message}`);
