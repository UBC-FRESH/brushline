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
  const execution=state.network["policy-execution"];
  if(execution){
   $("#schedule").innerHTML+=`<p class="schedule-note">Rolling year-one execution · median-cost episode ${execution.selection.episode_index} · year ${execution.selection.year}</p><table><tr><th>Metric</th><th>Policy year 1</th><th>Fixed year 1</th></tr><tr><td>Segment treatments</td><td>${execution.policy.actions}</td><td>${execution.fixed.actions}</td></tr><tr><td>Cost</td><td>${execution.policy.cost.toFixed(0)}</td><td>${execution.fixed.cost.toFixed(0)}</td></tr><tr><td>Crew-hours</td><td>${execution.policy.hours.toFixed(0)}</td><td>${execution.fixed.hours.toFixed(0)}</td></tr><tr><td>Tactical / work orders / shifts</td><td>${execution.policy.tactical_actions} / ${execution.policy.work_orders} / ${execution.policy.shift_assignments}</td><td>n/a</td></tr><tr><td>Feasibility</td><td>resource ${execution.policy.resource_feasible} · shift ${execution.policy.shift_feasible}</td><td>n/a</td></tr></table>`;
  }
  const scan=state.network["policy-execution-scan"];
  if(scan){
   $("#schedule").innerHTML+=`<p class="schedule-note">Policy execution scan · all ${scan.episodes} episodes · first year</p><table><tr><th>Check</th><th>Feasible share</th></tr><tr><td>Fully feasible</td><td>${(scan.execution_feasibility_rate*100).toFixed(1)}%</td></tr><tr><td>Access open</td><td>${(scan.access_open_rate*100).toFixed(1)}%</td></tr><tr><td>Resources</td><td>${(scan.resource_feasibility_rate*100).toFixed(1)}%</td></tr><tr><td>Shifts</td><td>${(scan.shift_feasibility_rate*100).toFixed(1)}%</td></tr><tr><td>First-year cost P10–P90</td><td>${scan.cost_band.p10.toFixed(0)}–${scan.cost_band.p90.toFixed(0)}</td></tr><tr><td>First-year crew-hours P10–P90</td><td>${scan.hours_band.p10.toFixed(0)}–${scan.hours_band.p90.toFixed(0)}</td></tr></table>`;
  }
  const staticPlan=state.network["static-robust"];
  if(staticPlan){
   const rows=(staticPlan.plans||[]).map(plan=>`<tr><td>${esc(plan.name)}${plan.name===staticPlan.recommended?" *":""}</td><td>${plan.nominal_budget.toFixed(0)}</td><td>${plan.cost_band.p10.toFixed(0)}–${plan.cost_band.p90.toFixed(0)}</td><td>${plan.risk.toFixed(4)}</td><td>${(plan.budget_violation_probability*100).toFixed(1)}%</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Static budget-headroom plans · actual budget 60000/yr · 20 episodes · * meets 5% budget-risk limit</p><table><tr><th>Candidate</th><th>Nominal budget</th><th>5-year cost P10–P90</th><th>Mean risk</th><th>Budget violation</th></tr>${rows}</table>`;
  }
  const stress=state.network["operational-stress"];
  if(stress){
   $("#schedule").innerHTML+=`<p class="schedule-note">Weather and outage stress · ${stress.scenarios} scenarios · ${stress.window_days}-day fall window · ${stress.outage_days.length}-day outage · ${(stress.weather_probability*100).toFixed(0)}% weather loss/day</p><table><tr><th>Metric</th><th>Baseline</th><th>Stress</th></tr><tr><td>Fully feasible</td><td>${stress.baseline.feasible}</td><td>${(stress.completion_probability*100).toFixed(1)}%</td></tr><tr><td>Mean completion</td><td>100%</td><td>${(stress.mean_completion_rate*100).toFixed(1)}%</td></tr><tr><td>Shift assignments</td><td>${stress.baseline.assignments}</td><td>${stress.shift_assignments_band.p50.toFixed(0)}</td></tr><tr><td>Unscheduled hours P50 / P90</td><td>${stress.baseline.unscheduled_hours.toFixed(0)}</td><td>${stress.unscheduled_hours_band.p50.toFixed(0)} / ${stress.unscheduled_hours_band.p90.toFixed(0)}</td></tr></table>`;
  }
  const stressScan=state.network["operational-stress-scan"];
  if(stressScan){
   const windowRows=(stressScan.window_sensitivity||[]).map(item=>`<tr><td>${item.window_days}</td><td>${(item.scenario_completion_rate*100).toFixed(1)}%</td><td>${item.mean_unscheduled_hours.toFixed(0)}</td></tr>`).join("");
   const sources=stressScan.failure_sources||{};
   $("#schedule").innerHTML+=`<p class="schedule-note">All-episode weather/outage scan · ${stressScan.episodes} episodes · ${stressScan.scenarios_per_episode} calendars each</p><table><tr><th>Metric</th><th>Value</th></tr><tr><td>Baseline 75-day feasible</td><td>${(stressScan.baseline_feasibility_rate*100).toFixed(1)}%</td></tr><tr><td>Scenario full completion</td><td>${(stressScan.scenario_completion_rate*100).toFixed(1)}%</td></tr><tr><td>Mean work completion</td><td>${(stressScan.mean_completion_rate*100).toFixed(1)}%</td></tr><tr><td>Unscheduled hours P50 / P90</td><td>${stressScan.unscheduled_hours_band.p50.toFixed(0)} / ${stressScan.unscheduled_hours_band.p90.toFixed(0)}</td></tr><tr><td>Failure sources</td><td>window ${sources.fall_window||0} · weather ${sources.weather_outage_calendar||0} · crew ${sources.crew_capacity||0} · none ${sources.none||0}</td></tr></table><table><tr><th>Window days</th><th>Scenario completion</th><th>Mean unscheduled h</th></tr>${windowRows}</table>`;
  }
  const remedies=state.network["operational-remedies"];
  if(remedies){
   const rows=(remedies.cases||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${(item.scenario_completion_rate*100).toFixed(1)}%</td><td>${(item.mean_completion_rate*100).toFixed(1)}%</td><td>${item.added_cost_band.p50.toFixed(0)}</td><td>${item.total_cost_band.p50.toFixed(0)}</td><td>${(item.budget_feasibility_rate*100).toFixed(1)}%</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Weather/outage remedies · ${remedies.episodes} episodes · ${remedies.scenarios_per_episode} calendars each · crew-day ${remedies.crew_day_cost.toFixed(0)} / machine-day ${remedies.machine_day_cost.toFixed(0)} CAD · best budget-feasible: ${esc(remedies.best_budget_feasible||"none")}</p><table><tr><th>Remedy</th><th>Scenario completion</th><th>Mean completion</th><th>Added cost P50</th><th>Total cost P50</th><th>Budget feasible</th></tr>${rows}</table>`;
  }
  const riskScope=state.network["risk-ranked-scope"];
  if(riskScope){
   const rows=(riskScope.cases||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${(item.scenario_completion_rate*100).toFixed(1)}%</td><td>${item.mean_risk_loss.toFixed(4)}</td><td>${item.mean_residual_risk.toFixed(4)}</td><td>${item.total_cost_band.p50.toFixed(0)}</td><td>${(item.budget_feasibility_rate*100).toFixed(1)}%</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Risk-ranked scope deferral · target ${(riskScope.target_fraction*100).toFixed(0)}% of first-year hours · whole actions deferred by lowest risk reduction per hour</p><table><tr><th>Case</th><th>Scenario completion</th><th>Mean risk loss</th><th>Residual risk</th><th>Total cost P50</th><th>Budget feasible</th></tr>${rows}</table>`;
  }
  const trajectory=state.network["risk-trajectory"];
  if(trajectory){
   const years=trajectory.years||[];
   const rows=(trajectory.cases||[]).map(item=>`<tr><td>${esc(item.name)}</td>${years.map((_,i)=>`<td>${item.annual_risk[i].toFixed(4)}</td>`).join("")}<td>${item.mean_risk_loss.toFixed(4)}</td><td>${item.final_risk_loss.toFixed(4)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Multi-year risk trajectory · first-year deferral · future actions held fixed · mean deferred ${(trajectory.mean_deferred_fraction*100).toFixed(1)}%</p><table><tr><th>Case</th>${years.map(year=>`<th>${year}</th>`).join("")}<th>Mean loss</th><th>Final loss</th></tr>${rows}</table>`;
  }
  const recovery=state.network["rolling-recovery"];
  if(recovery){
   const years=recovery.years||[];
   const rows=(recovery.cases||[]).map(item=>`<tr><td>${esc(item.name)}</td>${years.map((_,i)=>`<td>${item.annual_risk[i].toFixed(4)}</td>`).join("")}<td>${item.mean_risk_loss.toFixed(4)}</td><td>${item.final_risk_loss.toFixed(6)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Rolling recovery after first-year deferral · ${recovery.lookahead_years}-year lookahead · mean recovery ${recovery.mean_recovery.toFixed(4)} · final recovery ${recovery.final_recovery.toFixed(4)}</p><table><tr><th>Case</th>${years.map(year=>`<th>${year}</th>`).join("")}<th>Mean loss</th><th>Final loss</th></tr>${rows}</table>`;
  }
  const oos=state.network["out-of-sample-recovery"];
  if(oos){
   const f=oos.final_loss_band, rec=oos.recovery_band;
   $("#schedule").innerHTML+=`<p class="schedule-note">Out-of-sample future recovery · ${oos.paths_total} paths across ${oos.episodes} episodes · fixed first-year deferral</p><table><tr><th>Metric</th><th>P10</th><th>P50</th><th>P90</th><th>Mean</th></tr><tr><td>Final risk gap</td><td>${f.p10.toFixed(4)}</td><td>${f.p50.toFixed(4)}</td><td>${f.p90.toFixed(4)}</td><td>${f.mean.toFixed(4)}</td></tr><tr><td>Recovery</td><td>${rec.p10.toFixed(4)}</td><td>${rec.p50.toFixed(4)}</td><td>${rec.p90.toFixed(4)}</td><td>${rec.mean.toFixed(4)}</td></tr><tr><td>Final gap ≤ 0.005</td><td colspan="4">${(oos.probability_final_gap_at_most_0_005*100).toFixed(1)}% of paths</td></tr></table>`;
  }
  const frontier=state.network["deferral-frontier"];
  if(frontier){
   const rows=(frontier.cases||[]).map(item=>`<tr><td>${(item.target_fraction*100).toFixed(0)}%</td><td>${(item.mean_deferred_fraction*100).toFixed(1)}%</td><td>${(item.completion_75*100).toFixed(1)}%</td><td>${(item.completion_105*100).toFixed(1)}%</td><td>${item.fixed_future_final_loss.toFixed(4)}</td><td>${item.recovery_final_loss.toFixed(6)}</td><td>${item.reopt_cost_mean.toFixed(0)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Deferral-fraction frontier · risk-ranked first-year scope · fixed-factor recovery</p><table><tr><th>Target</th><th>Actual deferred</th><th>Completion 75</th><th>Completion 105</th><th>Fixed final loss</th><th>Recovery final loss</th><th>Reopt cost</th></tr>${rows}</table>`;
  }
  const validation=state.network["frontier-validation"];
  if(validation){
   const rows=(validation.cases||[]).map(item=>`<tr><td>${(item.target_fraction*100).toFixed(0)}%</td><td>${item.paths_total}</td><td>${item.final_loss_band.p50.toFixed(4)}</td><td>${item.final_loss_band.p90.toFixed(4)}</td><td>${item.recovery_band.p50.toFixed(4)}</td><td>${(item.probability_final_gap_at_most_0_005*100).toFixed(1)}%</td><td>${item.reopt_cost_band.p50.toFixed(0)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Frontier out-of-sample validation · 100 paths per target</p><table><tr><th>Target</th><th>Paths</th><th>Final gap P50</th><th>Final gap P90</th><th>Recovery P50</th><th>Within 0.005</th><th>Reopt cost P50</th></tr>${rows}</table>`;
  }
  const robust=state.network["robust-plan"];
  if(robust){
   const rows=(robust.test?.plans||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${item.cost_band.p10.toFixed(0)}–${item.cost_band.p90.toFixed(0)}</td><td>${item.risk.toFixed(4)}</td><td>${(item.budget_violation_probability*100).toFixed(1)}%</td><td>${(item.capacity_violation_probability*100).toFixed(1)}%</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Scenario-robust static plan · ${robust.training_paths} training paths · 100 test paths · not a distributional guarantee</p><table><tr><th>Plan</th><th>5-year cost P10–P90</th><th>Mean risk</th><th>Budget violation</th><th>Capacity violation</th></tr>${rows}</table>`;
  }
  const chance=state.network["chance-plan"];
  if(chance){
   const rows=(chance.test?.plans||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${item.cost_band.p10.toFixed(0)}–${item.cost_band.p90.toFixed(0)}</td><td>${item.risk.toFixed(4)}</td><td>${(item.budget_violation_probability*100).toFixed(1)}%</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Sampled budget chance constraint · ≤${chance.max_budget_violations} of ${chance.training_paths} paths/year · capacity hard · sampled, not distributional</p><table><tr><th>Plan</th><th>5-year cost P10–P90</th><th>Mean risk</th><th>Budget violation</th></tr>${rows}</table>`;
  }
  const chanceCapacity=state.network["chance-capacity-plan"];
  if(chanceCapacity){
   const rows=(chanceCapacity.test?.plans||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${item.cost_band.p10.toFixed(0)}–${item.cost_band.p90.toFixed(0)}</td><td>${item.risk.toFixed(4)}</td><td>${(item.budget_violation_probability*100).toFixed(1)}%</td><td>${(item.capacity_violation_probability*100).toFixed(1)}%</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Chance capacity · ≤${chanceCapacity.max_budget_violations} budget and ≤${chanceCapacity.max_capacity_violations} capacity violations/year on ${chanceCapacity.training_paths} paths · sampled</p><table><tr><th>Plan</th><th>5-year cost P10–P90</th><th>Mean risk</th><th>Budget violation</th><th>Capacity violation</th></tr>${rows}</table>`;
  }
  const chance100=state.network["chance-100-plan"];
  if(chance100){
   const rows=(chance100.test?.plans||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${item.cost_band.p10.toFixed(0)}–${item.cost_band.p90.toFixed(0)}</td><td>${item.risk.toFixed(4)}</td><td>${(item.budget_violation_probability*100).toFixed(1)}%</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">100-path budget chance · ≤${chance100.max_budget_violations} of ${chance100.training_paths} paths/year · capacity hard · sampled, not distributional</p><table><tr><th>Plan</th><th>5-year cost P10–P90</th><th>Mean risk</th><th>Budget violation</th></tr>${rows}</table>`;
  }
  const twoStage=state.network["two-stage-policy"];
  if(twoStage){
   $("#schedule").innerHTML+=`<p class="schedule-note">Two-stage operational recourse · first-year nominal plan · defer lowest risk reduction per hour until budget/capacity fit · 100 scenarios</p><table><tr><th>Metric</th><th>Static</th><th>Recourse</th></tr><tr><td>Budget violation</td><td>${(twoStage.static_budget_violation_probability*100).toFixed(1)}%</td><td>${(twoStage.recourse_budget_violation_probability*100).toFixed(1)}%</td></tr><tr><td>Capacity violation</td><td>${(twoStage.static_capacity_violation_probability*100).toFixed(1)}%</td><td>${(twoStage.recourse_capacity_violation_probability*100).toFixed(1)}%</td></tr><tr><td>Completion P50</td><td>${(twoStage.static_completion_band.p50*100).toFixed(1)}%</td><td>${(twoStage.recourse_completion_band.p50*100).toFixed(1)}%</td></tr><tr><td>Mean completion</td><td>100.0%</td><td>${(twoStage.recourse_completion_band.mean*100).toFixed(1)}%</td></tr><tr><td>Mean risk loss</td><td>0.0000</td><td>${twoStage.mean_risk_loss.toFixed(4)}</td></tr></table>`;
  }
  const multiStage=state.network["two-stage-multi"];
  if(multiStage){
   $("#schedule").innerHTML+=`<p class="schedule-note">Multi-year operational recourse · fixed five-year plan · annual deferral after factors · 100 scenarios</p><table><tr><th>Metric</th><th>Static</th><th>Recourse</th></tr><tr><td>Budget violation, any year</td><td>${(multiStage.static_budget_violation_probability*100).toFixed(1)}%</td><td>${(multiStage.recourse_budget_violation_probability*100).toFixed(1)}%</td></tr><tr><td>Capacity violation, any year</td><td>${(multiStage.static_capacity_violation_probability*100).toFixed(1)}%</td><td>${(multiStage.recourse_capacity_violation_probability*100).toFixed(1)}%</td></tr><tr><td>Completion P50</td><td>${(multiStage.static_completion_band.p50*100).toFixed(1)}%</td><td>${(multiStage.recourse_completion_band.p50*100).toFixed(1)}%</td></tr><tr><td>Mean completion</td><td>100.0%</td><td>${(multiStage.recourse_completion_band.mean*100).toFixed(1)}%</td></tr><tr><td>Mean risk</td><td>${multiStage.static_risk_band.mean.toFixed(4)}</td><td>${multiStage.recourse_risk_band.mean.toFixed(4)}</td></tr></table>`;
  }
  const rollingRecourse=state.network["rolling-recourse"];
  if(rollingRecourse){
   const rows=(rollingRecourse.cases||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${(item.budget_violation_probability*100).toFixed(1)}%</td><td>${(item.completion_band.p50*100).toFixed(1)}%</td><td>${(item.completion_band.mean*100).toFixed(1)}%</td><td>${item.risk_band.mean.toFixed(4)}</td><td>${item.cost_band.p50.toFixed(0)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Rolling policy with recourse · ${rollingRecourse.episodes} common-factor episodes · first-year fixed then rolling re-solves</p><table><tr><th>Policy</th><th>Budget violation</th><th>Completion P50</th><th>Mean completion</th><th>Mean risk</th><th>Cost P50</th></tr>${rows}</table>`;
  }
  const scaleRecourse=state.network["rolling-recourse-590"];
  if(scaleRecourse){
   const cases=(scaleRecourse.result||{}).cases||[];
   const rows=cases.map(item=>`<tr><td>${esc(item.name)}</td><td>${(item.budget_violation_probability*100).toFixed(1)}%</td><td>${(item.completion_band.p50*100).toFixed(1)}%</td><td>${item.risk_band.mean.toFixed(4)}</td><td>${item.cost_band.p50.toFixed(0)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">590-segment rolling recourse · replicated stress instance · ${scaleRecourse.episodes} episodes · fixed exact ${scaleRecourse.fixed_seconds.toFixed(1)}s · rolling heuristic ${scaleRecourse.rolling_seconds.toFixed(1)}s</p><table><tr><th>Policy</th><th>Budget violation</th><th>Completion P50</th><th>Mean risk</th><th>Cost P50</th></tr>${rows}</table>`;
  }
  const weatherRecourse=state.network["weather-recourse"];
  if(weatherRecourse){
   const calendar=weatherRecourse.calendar||{};
   const rows=(weatherRecourse.cases||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${(item.budget_violation_probability*100).toFixed(1)}%</td><td>${(item.completion_band.p50*100).toFixed(1)}%</td><td>${(item.retained_scope_band.p50*100).toFixed(1)}%</td><td>${item.risk_band.mean.toFixed(4)}</td><td>${item.cost_band.p50.toFixed(0)}</td><td>${item.mean_unscheduled_hours.toFixed(0)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Weather/outage-aware recourse · ${weatherRecourse.episodes} episodes · ${calendar.window_days}-day window · ${(calendar.outage_days||[]).length} outage days · ${(calendar.weather_probability*100).toFixed(0)}% loss/day · forecast + observed calendars</p><table><tr><th>Case</th><th>Budget violation</th><th>Completed scope P50</th><th>Retained scope P50</th><th>Mean risk</th><th>Cost P50</th><th>Unscheduled h</th></tr>${rows}</table>`;
  }
  const weatherScale=state.network["weather-recourse-590"];
  if(weatherScale){
   const rows=((weatherScale.result||{}).cases||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${(item.budget_violation_probability*100).toFixed(1)}%</td><td>${(item.completion_band.p50*100).toFixed(1)}%</td><td>${(item.retained_scope_band.p50*100).toFixed(1)}%</td><td>${item.risk_band.mean.toFixed(4)}</td><td>${item.cost_band.p50.toFixed(0)}</td><td>${item.mean_unscheduled_hours.toFixed(0)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">590-segment weather/outage-aware recourse · replicated stress instance · ${weatherScale.episodes} episodes · ${weatherScale.crews} crews · fixed exact ${weatherScale.fixed_seconds.toFixed(1)}s · weather ${weatherScale.rolling_seconds.toFixed(1)}s</p><table><tr><th>Case</th><th>Budget violation</th><th>Completed scope P50</th><th>Retained scope P50</th><th>Mean risk</th><th>Cost P50</th><th>Unscheduled h</th></tr>${rows}</table>`;
  }
  const forecastSkill=state.network["weather-forecast-skill"];
  if(forecastSkill){
   const rows=((forecastSkill.result||{}).cases||[]).map(item=>`<tr><td>${(item.forecast_skill*100).toFixed(0)}%</td><td>${(item.summary.completion_band.p50*100).toFixed(1)}%</td><td>${(item.summary.retained_scope_band.p50*100).toFixed(1)}%</td><td>${item.summary.risk_band.mean.toFixed(4)}</td><td>${item.summary.cost_band.p50.toFixed(0)}</td><td>${item.summary.mean_unscheduled_hours.toFixed(0)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Forecast-skill sensitivity · ${forecastSkill.episodes} episodes · skill = probability annual forecast equals actual · ${forecastSkill.seconds.toFixed(1)}s</p><table><tr><th>Skill</th><th>Completed scope P50</th><th>Retained scope P50</th><th>Mean risk</th><th>Cost P50</th><th>Unscheduled h</th></tr>${rows}</table>`;
  }
  const windowRemedy=state.network["weather-window-remedy"];
  if(windowRemedy){
   const rows=((windowRemedy.result||{}).cases||[]).map(item=>`<tr><td>${item.window_days}</td><td>${(item.summary.completion_band.p50*100).toFixed(1)}%</td><td>${(item.summary.retained_scope_band.p50*100).toFixed(1)}%</td><td>${item.summary.risk_band.mean.toFixed(4)}</td><td>${item.summary.cost_band.p50.toFixed(0)}</td><td>${item.summary.mean_unscheduled_hours.toFixed(0)}</td><td>${item.summary.mean_calendar_deferred_actions.toFixed(1)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Fall-window capacity remedy · observed-calendar awareness · ${windowRemedy.episodes} episodes · fixed crew mix · ${windowRemedy.seconds.toFixed(1)}s</p><table><tr><th>Window days</th><th>Completed scope P50</th><th>Retained scope P50</th><th>Mean risk</th><th>Cost P50</th><th>Unscheduled h</th><th>Calendar deferrals</th></tr>${rows}</table>`;
  }
  const windowRemedyScale=state.network["weather-window-remedy-590"];
  if(windowRemedyScale){
   const rows=((windowRemedyScale.result||{}).cases||[]).map(item=>`<tr><td>${item.window_days}</td><td>${(item.summary.completion_band.p50*100).toFixed(1)}%</td><td>${(item.summary.retained_scope_band.p50*100).toFixed(1)}%</td><td>${item.summary.risk_band.mean.toFixed(4)}</td><td>${item.summary.cost_band.p50.toFixed(0)}</td><td>${item.summary.mean_calendar_deferred_actions.toFixed(1)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">590-segment fall-window remedy · observed-calendar awareness · ${windowRemedyScale.episodes} episodes · ${windowRemedyScale.crews} crews · fixed exact ${windowRemedyScale.fixed_seconds.toFixed(1)}s · sweep ${windowRemedyScale.seconds.toFixed(1)}s</p><table><tr><th>Window days</th><th>Completed scope P50</th><th>Retained scope P50</th><th>Mean risk</th><th>Cost P50</th><th>Calendar deferrals</th></tr>${rows}</table>`;
  }
  const capacityRemedy=state.network["capacity-remedy"];
  if(capacityRemedy){
   const assumptions=capacityRemedy.assumptions||{};
   const rows=((capacityRemedy.result||{}).cases||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${item.window_days}</td><td>${item.extra_crews}</td><td>${(item.summary.completion_band.p50*100).toFixed(1)}%</td><td>${item.summary.risk_band.mean.toFixed(4)}</td><td>${item.summary.cost_band.p50.toFixed(0)}</td><td>${item.summary.mean_resource_cost.toFixed(0)}</td><td>${(item.summary.total_cost_band?.p50 ?? item.summary.cost_band.p50).toFixed(0)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">Added-crew versus window remedy · ${capacityRemedy.episodes} episodes · crew-day ${assumptions.crew_day_cost} · machine-day ${assumptions.machine_day_cost} · supervision ${(assumptions.supervision_fraction*100).toFixed(0)}% · overhead ${(assumptions.overhead_fraction*100).toFixed(0)}% · seasonal ${assumptions.seasonal_overhead_per_crew}/crew-year</p><table><tr><th>Case</th><th>Window days</th><th>Extra crews</th><th>Completed P50</th><th>Mean risk</th><th>Action cost P50</th><th>Added resource P50</th><th>Total cost P50</th></tr>${rows}</table>`;
  }
  const capacityRemedyScale=state.network["capacity-remedy-590"];
  if(capacityRemedyScale){
   const rows=((capacityRemedyScale.result||{}).cases||[]).map(item=>`<tr><td>${esc(item.name)}</td><td>${item.window_days}</td><td>${item.extra_crews}</td><td>${(item.summary.completion_band.p50*100).toFixed(1)}%</td><td>${item.summary.risk_band.mean.toFixed(4)}</td><td>${item.summary.cost_band.p50.toFixed(0)}</td><td>${item.summary.mean_resource_cost.toFixed(0)}</td><td>${(item.summary.total_cost_band?.p50 ?? item.summary.cost_band.p50).toFixed(0)}</td></tr>`).join("");
   $("#schedule").innerHTML+=`<p class="schedule-note">590-segment added-crew versus window remedy · ${capacityRemedyScale.episodes} episodes · ${capacityRemedyScale.crews} base crews · ${capacityRemedyScale.extra_crews} relief crews · fixed exact ${capacityRemedyScale.fixed_seconds.toFixed(1)}s · remedy ${capacityRemedyScale.seconds.toFixed(1)}s</p><table><tr><th>Case</th><th>Window days</th><th>Extra crews</th><th>Completed P50</th><th>Mean risk</th><th>Action cost P50</th><th>Added resource P50</th><th>Total cost P50</th></tr>${rows}</table>`;
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
