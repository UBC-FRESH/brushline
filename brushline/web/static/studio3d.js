import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

let renderer, scene, camera, controls, terrain, vegetation, group, block = null;
let pre = null, post = null, variant = "pre", walking = false, walkYaw = 0, walkPitch = 0;
let keys = new Set(), dragging = false, last = null, saved = null, real = null;
const eyeHeight = 1.7;

function terrainY(x, z) {
  if (!real) return 0.7 * Math.sin(x * 0.035) + 0.45 * Math.cos(z * 0.05) + 0.2 * Math.sin((x + z) * 0.08);
  const t = real.terrain, w = t.width, h = t.height, res = t.resolution_m;
  const col = Math.max(0, Math.min(w - 1, x / res)), row = Math.max(0, Math.min(h - 1, z / res));
  const c0 = Math.floor(col), r0 = Math.floor(row), c1 = Math.min(w - 1, c0 + 1), r1 = Math.min(h - 1, r0 + 1);
  const dc = col - c0, dr = row - r0;
  const v = (r, c) => t.elevation[r][c];
  return (v(r0,c0)*(1-dc)+v(r0,c1)*dc)*(1-dr) + (v(r1,c0)*(1-dc)+v(r1,c1)*dc)*dr;
}

function init() {
  const canvas = document.getElementById("scene");
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
  scene = new THREE.Scene();
  const sky = document.createElement("canvas");
  sky.width = 8; sky.height = 256;
  const skyGradient = sky.getContext("2d").createLinearGradient(0, 0, 0, 256);
  skyGradient.addColorStop(0, "#79a8c8");
  skyGradient.addColorStop(0.55, "#b9d2d1");
  skyGradient.addColorStop(1, "#e2ece2");
  const skyContext = sky.getContext("2d");
  skyContext.fillStyle = skyGradient; skyContext.fillRect(0, 0, 8, 256);
  const skyTexture = new THREE.CanvasTexture(sky);
  skyTexture.colorSpace = THREE.SRGBColorSpace;
  scene.background = skyTexture;
  scene.fog = new THREE.Fog("#dce9e2", 900, 2800);
  camera = new THREE.PerspectiveCamera(58, canvas.clientWidth / canvas.clientHeight, 0.1, 5000);
  camera.position.set(40, 55, 120);
  controls = new OrbitControls(camera, canvas);
  controls.target.set(50, 2, 0);
  controls.maxPolarAngle = Math.PI * 0.48;
  scene.add(new THREE.HemisphereLight("#ffffff", "#405c45", 1.5));
  const sun = new THREE.DirectionalLight("#fff4d6", 2.2);
  sun.position.set(80, 140, 60);
  scene.add(sun);
  canvas.addEventListener("click", () => {
    if (walking && document.pointerLockElement !== canvas) canvas.requestPointerLock?.();
  });
  canvas.addEventListener("pointerdown", (e) => { if (walking) { dragging = true; last = {x: e.clientX, y: e.clientY}; } });
  canvas.addEventListener("pointerup", () => { dragging = false; last = null; });
  document.addEventListener("pointerlockchange", () => { last = null; });
  document.addEventListener("mousemove", (e) => {
    if (!walking) return;
    let dx = 0, dy = 0;
    if (document.pointerLockElement === canvas) { dx = e.movementX || 0; dy = e.movementY || 0; }
    else if (dragging && last) { dx = e.clientX - last.x; dy = e.clientY - last.y; last = {x: e.clientX, y: e.clientY}; }
    else return;
    walkYaw -= dx * 0.0022;
    walkPitch = Math.max(-1.2, Math.min(0.8, walkPitch - dy * 0.002));
  });
  document.addEventListener("keydown", (e) => {
    if (!walking) return;
    if (["w","a","s","d","W","A","S","D"].includes(e.key)) { keys.add(e.key.toLowerCase()); e.preventDefault(); }
    if (e.key === "Escape") { setWalking(false); window.dispatchEvent(new CustomEvent("brushline:exit-walk")); }
  });
  document.addEventListener("keyup", (e) => keys.delete(e.key.toLowerCase()));
  window.addEventListener("resize", resize);
  new ResizeObserver(resize).observe(canvas);
  animate();
}

function resize() {
  const canvas = renderer.domElement;
  renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
  camera.aspect = canvas.clientWidth / Math.max(1, canvas.clientHeight);
  camera.updateProjectionMatrix();
}

function build(sceneData, nextVariant) {
  if (sceneData.schema_version === "brushline.real-scene.v1") { buildReal(sceneData); return; }
  real = null;
  block = sceneData;
  variant = nextVariant || variant;
  if (group) scene.remove(group);
  group = new THREE.Group();
  scene.add(group);
  const pts = sceneData.geometry?.points?.length
    ? sceneData.geometry.points
    : [[0,0],[100,0]];
  const centerX = pts.reduce((s,p)=>s+p[0],0)/pts.length;
  const centerZ = pts.reduce((s,p)=>s+p[1],0)/pts.length;
  const span = Math.max(80, ...pts.map(p=>Math.abs(p[0]-centerX)+Math.abs(p[1]-centerZ))) * 2 + 60;

  const plane = new THREE.PlaneGeometry(span, span, 48, 48);
  plane.rotateX(-Math.PI / 2);
  const pos = plane.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i) + centerX, z = pos.getZ(i) + centerZ;
    pos.setY(i, terrainY(x, z));
  }
  plane.computeVertexNormals();
  terrain = new THREE.Mesh(plane, new THREE.MeshStandardMaterial({color:"#78977d", roughness:.95}));
  terrain.position.set(centerX, 0, centerZ);
  group.add(terrain);
  const grid = new THREE.GridHelper(span, 20, "#5b7662", "#698671");
  grid.position.set(centerX, 0.03, centerZ);
  group.add(grid);

  const corridor = new THREE.BufferGeometry();
  const width = sceneData.geometry?.width_m || 8;
  const left = [], right = [], index = [];
  pts.forEach((p, i) => {
    const prev = pts[Math.max(0,i-1)], next = pts[Math.min(pts.length-1,i+1)];
    const dx = next[0]-prev[0], dz = next[1]-prev[1], len = Math.hypot(dx,dz) || 1;
    const nx = -dz/len*width/2, nz = dx/len*width/2;
    left.push(p[0]+nx, terrainY(p[0],p[1])+0.06, p[1]+nz);
    right.push(p[0]-nx, terrainY(p[0],p[1])+0.06, p[1]-nz);
    if (i < pts.length-1) index.push(i*2, i*2+1, i*2+2, i*2+1, i*2+3, i*2+2);
  });
  corridor.setAttribute("position", new THREE.Float32BufferAttribute([...left, ...right], 3));
  corridor.setIndex(index);
  corridor.computeVertexNormals();
  group.add(new THREE.Mesh(corridor, new THREE.MeshStandardMaterial({color:"#8a6d4b", roughness:1})));

  const veg = sceneData.vegetation || {};
  const count = Math.max(24, Math.round((veg.cover_pct || 30) * 1.2));
  const geometry = new THREE.ConeGeometry(1.2, 3.6, 7);
  const material = new THREE.MeshStandardMaterial({color: veg.functional_group === "conifer" ? "#285c3c" : "#4c8b53", roughness:.9});
  vegetation = new THREE.InstancedMesh(geometry, material, count);
  pre = []; post = [];
  for (let i = 0; i < count; i++) {
    const t = (i + .5) / count;
    const idx = Math.min(pts.length-2, Math.floor(t * (pts.length-1)));
    const local = t * (pts.length-1) - idx;
    const x = pts[idx][0] + (pts[idx+1][0]-pts[idx][0]) * local;
    const z = pts[idx][1] + (pts[idx+1][1]-pts[idx][1]) * local;
    const offset = Math.sin(i * 12.9898) * width * 0.42;
    const dx = pts[idx+1][0]-pts[idx][0], dz = pts[idx+1][1]-pts[idx][1];
    const len = Math.hypot(dx,dz) || 1;
    const px = x + (-dz/len)*offset, pz = z + (dx/len)*offset;
    const h = (veg.height_m || 2) * (0.75 + 0.25 * Math.abs(Math.sin(i * 4.1)));
    pre.push({x:px, z:pz, h});
    post.push({x:px, z:pz, h:h * 0.5});
    setInstance(i, pre[i]);
  }
  group.add(vegetation);
  // A simple structure marker at each end.
  for (const p of [pts[0], pts[pts.length-1]]) {
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(.12,.12,7,6), new THREE.MeshStandardMaterial({color:"#4b5350"}));
    pole.position.set(p[0], terrainY(p[0],p[1])+3.5, p[1]);
    group.add(pole);
  }
  const dist = Math.max(34, span * 0.32);
  camera.position.set(centerX + dist * 0.42, Math.max(18, dist * 0.34), centerZ + dist * 0.92);
  controls.target.set(centerX, 2, centerZ);
  controls.update();
  applyVariant();
}


function buildReal(data) {
  block = data; real = data; variant = "pre";
  if (group) scene.remove(group);
  group = new THREE.Group(); scene.add(group);
  const t = data.terrain, w = t.width, h = t.height, res = t.resolution_m;
  const verts = [], idx = [];
  for (let r = 0; r < h; r++) for (let c = 0; c < w; c++) verts.push(c*res, t.elevation[r][c], r*res);
  for (let r = 0; r < h-1; r++) for (let c = 0; c < w-1; c++) {
    const a=r*w+c, b=a+1, d=a+w, e=d+1; idx.push(a,d,b,b,d,e);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(verts,3));
  geo.setIndex(idx); geo.computeVertexNormals();
  group.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({color:"#78977d", roughness:.95})));
  const power = data.powerline || null;
  const linePoints = [];
  if (power) {
    const cw = 70;
    (power.lines || []).forEach((line) => {
      const pts = line.points || [];
      if (pts.length < 2) return;
      const verts = [], idx = [];
      pts.forEach((p, i) => {
        const prev = pts[Math.max(0,i-1)], next = pts[Math.min(pts.length-1,i+1)];
        const dx = next[0]-prev[0], dz = next[1]-prev[1], len = Math.hypot(dx,dz) || 1;
        const nx = -dz/len*cw/2, nz = dx/len*cw/2;
        verts.push(p[0]+nx, terrainY(p[0]+nx,p[1]+nz)+0.08, p[1]+nz);
        verts.push(p[0]-nx, terrainY(p[0]-nx,p[1]-nz)+0.08, p[1]-nz);
        if (i < pts.length-1) idx.push(i*2,i*2+1,i*2+2,i*2+1,i*2+3,i*2+2);
      });
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(verts,3)); g.setIndex(idx); g.computeVertexNormals();
      group.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({color:'#9a8b6a', roughness:1})));
      linePoints.push(pts);
    });
  }
  const distanceToLine = (x,z) => {
    let best = 1e9;
    linePoints.forEach((pts) => {
      for (let i=0;i<pts.length-1;i++) {
        const [x1,z1]=pts[i], [x2,z2]=pts[i+1];
        const dx=x2-x1, dz=z2-z1, l2=dx*dx+dz*dz;
        const f=l2 ? Math.max(0,Math.min(1,((x-x1)*dx+(z-z1)*dz)/l2)) : 0;
        best=Math.min(best, Math.hypot(x-(x1+f*dx), z-(z1+f*dz)));
      }
    });
    return best;
  };
  const trees = (data.trees || []).filter((tree) => !power || distanceToLine(tree.x_m, tree.y_m) > 36);
  const trunkGeo = new THREE.CylinderGeometry(.18,.23,1,5);
  const crownGeo = new THREE.SphereGeometry(1,7,6);
  const trunks = new THREE.InstancedMesh(trunkGeo, new THREE.MeshStandardMaterial({color:"#5b4433"}), trees.length);
  const crowns = new THREE.InstancedMesh(crownGeo, new THREE.MeshStandardMaterial({color:"#3f7a4b", roughness:.9}), trees.length);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  trees.forEach((tree,i) => {
    const y = terrainY(tree.x_m, tree.y_m), hh = Math.max(1, tree.height_m), cw = Math.max(1, tree.crown_width_m || hh*.3);
    m.compose(new THREE.Vector3(tree.x_m, y+hh*.35, tree.y_m), q, s.set(1,hh*.7,1)); trunks.setMatrixAt(i,m);
    m.compose(new THREE.Vector3(tree.x_m, y+hh*.78, tree.y_m), q, s.set(cw*.5,hh*.34,cw*.5)); crowns.setMatrixAt(i,m);
  });
  group.add(trunks); group.add(crowns);
  if (power) {
    const towerMat = new THREE.MeshStandardMaterial({color:"#4f5e5b", metalness:.45, roughness:.6});
    (power.towers || []).forEach((tower) => {
      const g = new THREE.Group();
      const h = tower.height_m || 45;
      const mast = new THREE.Mesh(new THREE.CylinderGeometry(1.8,2.3,h,8), towerMat);
      mast.position.y = h/2; g.add(mast);
      for (const [dx,dz] of [[-1.6,-1.6],[1.6,-1.6],[-1.6,1.6],[1.6,1.6]]) {
        const leg = new THREE.Mesh(new THREE.CylinderGeometry(.5,.75,h,5), towerMat);
        leg.position.set(dx,h/2,dz); g.add(leg);
      }
      for (const [w, y] of [[13,.72],[9,.84],[5,.95]]) {
        const arm = new THREE.Mesh(new THREE.BoxGeometry(w,.55,.7), towerMat);
        arm.position.set(0,h*y,0); g.add(arm);
      }
      g.position.set(tower.x_m, terrainY(tower.x_m,tower.y_m), tower.y_m); group.add(g);
    });
    (power.lines || []).forEach((line) => {
      const pts = (line.points || []).map(([x,z]) => new THREE.Vector3(x, terrainY(x,z)+(power.conductor_height_m||32), z));
      if (pts.length > 1) {
        const curve = new THREE.CatmullRomCurve3(pts);
        group.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 64, 1.0, 6, false), new THREE.MeshStandardMaterial({color:'#202b29', roughness:.25})));
      }
    });
  }
  const center = [w*res/2, h*res/2];
  const span = Math.max(w*res, h*res);
  if (power && power.towers?.length) {
    const tower = power.towers[0];
    camera.position.set(tower.x_m + 180, terrainY(tower.x_m, tower.y_m) + 110, tower.y_m + 220);
    controls.target.set(tower.x_m, terrainY(tower.x_m, tower.y_m) + 25, tower.y_m);
  } else {
    camera.position.set(center[0]+span*.35, 150, center[1]+span*.55);
    controls.target.set(center[0], 45, center[1]);
  }
  controls.update();
  applyVariant();
}

function setInstance(i, item) {
  const m = new THREE.Matrix4();
  m.compose(
    new THREE.Vector3(item.x, terrainY(item.x,item.z)+item.h/2, item.z),
    new THREE.Quaternion(),
    new THREE.Vector3(1, item.h/3.6, 1)
  );
  vegetation.setMatrixAt(i, m);
  vegetation.instanceMatrix.needsUpdate = true;
}

function applyVariant() {
  if (real) { document.getElementById("variant").textContent = "observed"; return; }
  if (!vegetation) return;
  const data = variant === "post" ? post : pre;
  data.forEach((item, i) => setInstance(i, item));
  document.getElementById("variant").textContent = variant;
}

function setWalking(on) {
  walking = on;
  controls.enabled = !on;
  const canvas = renderer.domElement;
  if (on) {
    saved = {position: camera.position.clone(), quaternion: camera.quaternion.clone(), target: controls.target.clone(), fov: camera.fov};
    camera.fov = 68; camera.updateProjectionMatrix();
    let start = [0,0], target = [100,0];
    if (real?.powerline?.lines?.length) {
      const pts = real.powerline.lines[0].points || [];
      const mid = pts[Math.floor(pts.length/2)] || [0,0];
      const next = pts[Math.min(pts.length-1, Math.floor(pts.length/2)+1)] || mid;
      const dx = next[0]-mid[0], dz = next[1]-mid[1], len = Math.hypot(dx,dz) || 1;
      start = [mid[0] - dz/len*14, mid[1] + dx/len*14];
      target = [start[0] + dx/len*100, start[1] + dz/len*100];
    } else if (real) { start = [20,20]; target = [real.terrain.width*real.terrain.resolution_m/2, real.terrain.height*real.terrain.resolution_m/2]; }
    else if (block?.geometry?.points?.length) { start = block.geometry.points[0]; target = block.geometry.points[block.geometry.points.length-1]; }
    camera.position.set(start[0], terrainY(start[0],start[1])+eyeHeight, start[1]);
    walkYaw = Math.atan2(-(target[0]-start[0]), -(target[1]-start[1]));
    walkPitch = 0.02;
    camera.rotation.set(walkPitch, walkYaw, 0, "YXZ");
    canvas.focus();
  } else {
    if (document.pointerLockElement === canvas) document.exitPointerLock();
    if (saved) {
      camera.position.copy(saved.position); camera.quaternion.copy(saved.quaternion);
      camera.fov = saved.fov; camera.updateProjectionMatrix(); controls.target.copy(saved.target); controls.update();
    }
  }
  document.getElementById("walk").textContent = on ? "Exit walkthrough" : "Walk this block";
  document.getElementById("walk-hud").hidden = !on;
}

function animate() {
  requestAnimationFrame(animate);
  if (walking) {
    const speed = keys.has("shift") ? 8 : 3;
    const forward = new THREE.Vector3(-Math.sin(walkYaw), 0, -Math.cos(walkYaw));
    const right = new THREE.Vector3(Math.cos(walkYaw), 0, -Math.sin(walkYaw));
    const move = new THREE.Vector3();
    if (keys.has("w")) move.add(forward);
    if (keys.has("s")) move.sub(forward);
    if (keys.has("d")) move.add(right);
    if (keys.has("a")) move.sub(right);
    if (move.lengthSq() > 0) {
      move.normalize().multiplyScalar(speed * 0.016);
      camera.position.add(move);
    }
    camera.position.y = terrainY(camera.position.x, camera.position.z) + eyeHeight;
    camera.rotation.set(walkPitch, walkYaw, 0, "YXZ");
    const hud = document.getElementById("walk-hud");
    if (hud) hud.textContent = `${block?.block?.block_id || "block"} · ${variant} · heading ${Math.round((-walkYaw*180/Math.PI+360)%360)}° · ${camera.position.x.toFixed(0)}, ${camera.position.z.toFixed(0)} · context view`;
  } else {
    controls.update();
  }
  renderer.render(scene, camera);
}

window.brushline3d = {
  setScene(data, nextVariant) {
    if (block && block.block?.block_id === data.block?.block_id && vegetation) {
      block = data; variant = nextVariant || variant; applyVariant(); return;
    }
    build(data, nextVariant);
  },
  setVariant(next) { variant = next; applyVariant(); },
  setWalking,
  isWalking: () => walking,
  focusPower: () => {
    const tower = block?.powerline?.towers?.[0];
    if (!tower) return;
    camera.position.set(tower.x_m + 180, terrainY(tower.x_m, tower.y_m) + 110, tower.y_m + 220);
    controls.target.set(tower.x_m, terrainY(tower.x_m, tower.y_m) + 25, tower.y_m);
    controls.update();
  },
  debug: () => ({children: scene?.children.length, camera: camera?.position.toArray(), block: !!block, group: !!group, groupChildren: group?.children.length}),
};
init();
