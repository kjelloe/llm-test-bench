// Excerpts from CarrierDominion client/render/world.js (commit 527e5f1), one part per
// function. Model space: x toward the bow, y up, z toward starboard. Each function's
// mesh is added to a THREE.Group at the model's origin. canopy is adapted for this task
// (the game uses a SphereGeometry there and no rotation).

export function carrierBow(group, deckMaterial) {
  // Rotate the GEOMETRY, not the mesh: composing two Euler angles on the mesh
  // makes the bow point somewhere diagonal, which is exactly the cue the
  // player uses to read heading.
  const bowGeometry = new THREE.ConeGeometry(36, 70, 4);
  bowGeometry.rotateY(Math.PI / 4);
  bowGeometry.rotateZ(-Math.PI / 2);
  const bow = new THREE.Mesh(bowGeometry, deckMaterial);
  bow.position.set(195, 10, 0);
  group.add(bow);
}

export function mantaDelta(group, teamMat) {
  // The delta: a flattened three-sided cone pointing down +x.
  const deltaGeometry = new THREE.ConeGeometry(13, 30, 3);
  deltaGeometry.rotateZ(-Math.PI / 2);
  deltaGeometry.scale(1, 0.16, 1.7);
  const delta = new THREE.Mesh(deltaGeometry, teamMat);
  delta.position.x = -3;
  group.add(delta);
}

export function mantaNose(group, trimMat) {
  const noseGeometry = new THREE.ConeGeometry(2.2, 8, 6);
  noseGeometry.rotateZ(-Math.PI / 2);
  const nose = new THREE.Mesh(noseGeometry, trimMat);
  nose.position.set(17, 2.2, 0);
  group.add(nose);
}

export function mantaFin(group, trimMat, side) { // side: -1 port, 1 starboard
  const fin = new THREE.Mesh(new THREE.BoxGeometry(7, 6, 0.8), trimMat);
  fin.position.set(-9, 4.5, side * 5.5);
  fin.rotation.x = side * -0.35;
  group.add(fin);
}

export function lighterBow(group, teamMat) {
  const bowGeometry = new THREE.CylinderGeometry(0.1, 5.5, 8, 4);
  bowGeometry.rotateZ(-Math.PI / 2);
  bowGeometry.rotateX(Math.PI / 4);
  const bow = new THREE.Mesh(bowGeometry, teamMat);
  bow.position.set(16.5, 3, 0);
  group.add(bow);
}

export function walrusWheel(group, darkMat) {
  const wheelGeometry = new THREE.CylinderGeometry(2.2, 2.2, 1.6, 8);
  wheelGeometry.rotateX(Math.PI / 2);
  const wheel = new THREE.Mesh(wheelGeometry, darkMat);
  wheel.position.set(-5, 2.2, 5.1);
  group.add(wheel);
}

export function turretRail(group, railMat) {
  const rail = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.6, 34, 5), railMat);
  rail.geometry.rotateZ(-Math.PI / 2.6);
  rail.position.set(-4, 44, -12);
  group.add(rail);
}

export function crane(group, trimMat) {
  const craneGeometry = new THREE.CylinderGeometry(1.6, 2.2, 42, 6);
  craneGeometry.rotateZ(0.7);
  const crane = new THREE.Mesh(craneGeometry, trimMat);
  crane.position.set(-150, 40, 14);
  group.add(crane);
}

export function dish(group, lightMat) {
  const dish = new THREE.Mesh(new THREE.CylinderGeometry(7, 7, 2, 10), lightMat);
  dish.rotation.x = 0.9;
  dish.position.set(-30, 78, 26);
  group.add(dish);
}

export function canopy(group, canopyMat) {
  const canopy = new THREE.Mesh(new THREE.BoxGeometry(5.2, 5.2, 5.2), canopyMat);
  canopy.scale.set(1.9, 0.9, 1);
  canopy.rotation.y = 0.3;
  canopy.position.set(7, 4.2, 0);
  group.add(canopy);
}
