// three.js r162 light setups from the browser clients (colour management on, the r162 default).

// boombrawl client/renderer.js (commit e807b68)

  const scene = new THREE.Scene();
  scene.add(new THREE.AmbientLight(0xaab4ff, 1.0));
  const sun = new THREE.DirectionalLight(0xffffff, 1.7);
  sun.position.set(6, 14, 4);
  scene.add(sun);


// CarrierDominion client/render/scene.js (commit 7daf882)
function createLights(scene, preset, sizeMetres, style) {
  const hemi = new THREE.HemisphereLight(0xbcd8f0, 0x35506a, style.hemiIntensity);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xfff2df, style.sunIntensity);
  // Aim the sun at the middle of the map, not at the scene origin: the origin
  // is the map's south-west CORNER, so a default-target sun lights the sea and
  // leaves every hull in the archipelago as a silhouette.
  const centre = new THREE.Object3D();
  centre.position.set(sizeMetres / 2, 0, -sizeMetres / 2);
  scene.add(centre);
  sun.target = centre;
  sun.position.set(sizeMetres * 0.9, sizeMetres * 0.6, -sizeMetres * 0.15);
  if (preset.shadows) {
    sun.castShadow = true;
  // ... shadows ...
  scene.add(sun);
  // A weak fill from the opposite quarter. Without it a hull is a silhouette
  // whenever the chase camera happens to sit between the sun and the ship,
  // which is most of the time.
  const fill = new THREE.DirectionalLight(0xc8dcf0, 0.45);
  fill.position.set(-sizeMetres * 0.4, sizeMetres * 0.3, sizeMetres * 0.6);
  fill.target = centre;
  scene.add(fill);
  return { sun: sun, hemi: hemi };
}
