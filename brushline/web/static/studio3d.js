import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

let renderer, scene, camera, controls, terrain, vegetation, group, block = null;
let pre = null, post = null, variant = "pre", walking = false, walkYaw = 0, walkPitch = 0;
let keys = new Set(), dragging = false, last = null, saved = null;
const eyeHeight = 1.7;

function terrainY(x, z) {
  return 0.7 * Math.sin(x * 0.035) + 0.45 * Math.cos(z * 0.05) + 0.2 * Math.sin((x + z) * 0.08);
}

function init() {
  const canvas = document.getElementById("scene");
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
  scene = new THREE.Scene();
  scene.background = new THREE.Color("#b9d0c1");
  scene.fog = new THREE.Fog("#b9d0c1", 220, 620);
  camera = new THREE.PerspectiveCamera(58, canvas.clientWidth / canvas.clientHeight, 0.1, 1200);
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
    const pts = block?.geometry?.points?.length ? block.geometry.points : [[0,0],[100,0]];
    camera.position.set(pts[0][0], terrainY(pts[0][0],pts[0][1])+eyeHeight, pts[0][1]);
    walkYaw = Math.atan2(-(pts[1][0]-pts[0][0]), -(pts[1][1]-pts[0][1]));
    walkPitch = -0.04;
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
  debug: () => ({children: scene?.children.length, camera: camera?.position.toArray(), block: !!block, group: !!group, groupChildren: group?.children.length}),
};
init();
