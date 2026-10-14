// Writes the test fixtures to stdout: random scenes built with three r162's own classes (js/three.reference.mjs),
// projected and sorted exactly as WebGLRenderer.projectObject and WebGLRenderList do (see js/three-r162-renderlist.js;
// the two sort functions are taken from three's source text, not retyped).
// node js/make-fixtures.reference.mjs > tests/FastengineTests/fixtures.json
import { readFileSync } from 'node:fs';
import * as THREE from './three.reference.mjs';

const src = readFileSync( new URL( './three.reference.mjs', import.meta.url ), 'utf8' );
const fn = ( name ) => new Function( src.match( new RegExp( `function ${name}\\( a, b \\) \\{[\\s\\S]*?\\n\\}\\n` ) )[ 0 ] + `return ${name};` )();
const painterSortStable = fn( 'painterSortStable' );
const reversePainterSortStable = fn( 'reversePainterSortStable' );

let seed = 162;
function rnd() { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul( seed ^ seed >>> 15, 1 | seed ); t = t + Math.imul( t ^ t >>> 7, 61 | t ) ^ t; return ( ( t ^ t >>> 14 ) >>> 0 ) / 4294967296; }
const pick = ( a ) => a[ Math.floor( rnd() * a.length ) ];
const range = ( lo, hi ) => lo + ( hi - lo ) * rnd();
const r3 = ( x ) => Math.round( x * 1000 ) / 1000;

function project( scene, camera ) {
	scene.updateMatrixWorld();
	camera.updateMatrixWorld();
	const proj = new THREE.Matrix4().multiplyMatrices( camera.projectionMatrix, camera.matrixWorldInverse );
	const lists = { opaque: [], transmissive: [], transparent: [] };
	const v = new THREE.Vector3();
	const frustum = new THREE.Frustum().setFromProjectionMatrix( proj );   // three's own culling code
	const push = ( object, m, groupOrder, z ) => {
		const item = { id: object.id, material: m, groupOrder, renderOrder: object.renderOrder, z };
		( m.transmission > 0 ? lists.transmissive : m.transparent === true ? lists.transparent : lists.opaque ).push( item );
	};
	( function projectObject( object, groupOrder ) {
		if ( object.visible === false ) return;
		if ( ! object.layers.test( camera.layers ) ) { /* not drawn, but its children are still visited */ }
		else if ( object.isGroup ) groupOrder = object.renderOrder;
		else if ( object.isLight ) { /* lights are collected, not drawn */ }
		else if ( object.isSprite ) {
			if ( object.frustumCulled && ! frustum.intersectsSprite( object ) ) { /* culled */ } else {
				v.setFromMatrixPosition( object.matrixWorld ).applyMatrix4( proj );
				if ( object.material.visible ) push( object, object.material, groupOrder, v.z );
			}
		} else if ( ( object.isMesh || object.isLine || object.isPoints ) && object.frustumCulled && ! frustum.intersectsObject( object ) ) {
			/* culled */
		} else if ( object.isMesh || object.isLine || object.isPoints ) {
			v.copy( object.geometry.boundingSphere.center ).applyMatrix4( object.matrixWorld ).applyMatrix4( proj );
			const material = object.material;
			if ( Array.isArray( material ) ) {
				for ( const group of object.geometry.groups ) {
					const gm = material[ group.materialIndex ];
					if ( gm && gm.visible ) push( object, gm, groupOrder, v.z );
				}
			} else if ( material.visible ) push( object, material, groupOrder, v.z );
		}
		for ( const child of object.children ) projectObject( child, groupOrder );
	} )( scene, 0 );
	lists.opaque.sort( painterSortStable );
	lists.transmissive.sort( reversePainterSortStable );
	lists.transparent.sort( reversePainterSortStable );
	return { proj, lists };
}

function node( o ) {
	const kind = o.isGroup ? 'group' : o.isLight ? 'light' : o.isSprite ? 'sprite' : o.isMesh ? 'mesh' : o.isLine ? 'line'
		: o.isPoints ? 'points' : 'object';
	const n = { id: o.id, kind, renderOrder: o.renderOrder, visible: o.visible, world: Array.from( o.matrixWorld.elements ),
		frustumCulled: o.frustumCulled, layers: o.layers.mask };
	const mat = ( m ) => ( { id: m.id, transparent: m.transparent, transmission: m.transmission ?? 0, visible: m.visible } );
	if ( o.isMesh || o.isLine || o.isPoints || o.isSprite ) {
		if ( ! o.isSprite ) { n.center = o.geometry.boundingSphere.center.toArray(); n.radius = o.geometry.boundingSphere.radius; }
		if ( Array.isArray( o.material ) ) {
			n.materials = o.material.map( mat );
			n.groupMaterials = o.geometry.groups.map( ( g ) => g.materialIndex );
		} else n.material = mat( o.material );
	}
	n.children = o.children.map( node );
	return n;
}

function material( kind ) {
	const m = new THREE.MeshPhysicalMaterial();
	if ( kind === 'transparent' ) m.transparent = true;
	if ( kind === 'transmissive' ) m.transmission = 0.5;
	return m;
}

function mesh( materials, opts ) {
	const g = new THREE.BufferGeometry();
	g.boundingSphere = new THREE.Sphere( new THREE.Vector3( ...( opts.center ?? [ 0, 0, 0 ] ) ), opts.radius ?? 1 );
	const o = new THREE.Mesh( g, opts.material ?? pick( materials ) );
	o.position.set( ...( opts.position ?? [ r3( range( -8, 8 ) ), r3( range( -3, 3 ) ), r3( range( -30, -2 ) ) ] ) );
	o.rotation.set( r3( range( -1, 1 ) ), r3( range( -3, 3 ) ), 0 );
	o.renderOrder = opts.renderOrder ?? pick( [ 0, 0, 0, 0, 1, -1 ] );
	o.frustumCulled = opts.culled ?? false;
	return o;
}

function camera() {
	const c = new THREE.PerspectiveCamera( pick( [ 45, 60, 75 ] ), pick( [ 16 / 9, 4 / 3 ] ), 0.1, 500 );
	c.position.set( r3( range( -2, 2 ) ), r3( range( 0, 3 ) ), r3( range( 0, 4 ) ) );
	c.lookAt( r3( range( -3, 3 ) ), 0, -15 );
	return c;
}

const cases = [];
function add( name, scene, cam ) {
	const { proj, lists } = project( scene, cam );
	scene.updateMatrixWorld();
	cases.push( { name, viewProjection: Array.from( proj.elements ), cameraPosition: cam.position.toArray(), cameraLayers: cam.layers.mask,
		scene: node( scene ),
		opaque: lists.opaque.map( ( i ) => i.id ), transmissive: lists.transmissive.map( ( i ) => i.id ), transparent: lists.transparent.map( ( i ) => i.id ) } );
}

// Hand-made cases, one trap each.
{	// Off-axis: euclidean distance and projected depth disagree.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const glass = material( 'transparent' );
	s.add( mesh( [ glass ], { position: [ 0, 0, -10 ], renderOrder: 0 } ) );
	s.add( mesh( [ glass ], { position: [ 9, 0, -9 ], renderOrder: 0 } ) );
	s.add( mesh( [ glass ], { position: [ -6, 0, -9.5 ], renderOrder: 0 } ) );
	add( 'off_axis_depth_not_distance', s, c );
}
{	// The bounding sphere's centre decides, not the object's origin.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const glass = material( 'transparent' );
	const a = mesh( [ glass ], { position: [ 0, 0, -10 ], center: [ 0, 0, 6 ], renderOrder: 0 } ); a.rotation.set( 0, 0, 0 );
	const b = mesh( [ glass ], { position: [ 0.5, 0, -6 ], renderOrder: 0 } ); b.rotation.set( 0, 0, 0 );
	s.add( a, b );
	add( 'bounding_centre_not_origin', s, c );
}
{	// Opaque: material id before depth.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const m1 = material( 'opaque' ), m2 = material( 'opaque' );
	s.add( mesh( [], { material: m2, position: [ 0, 0, -3 ], renderOrder: 0 } ) );
	s.add( mesh( [], { material: m1, position: [ 0, 0, -20 ], renderOrder: 0 } ) );
	s.add( mesh( [], { material: m2, position: [ 0, 0, -12 ], renderOrder: 0 } ) );
	s.add( mesh( [], { material: m1, position: [ 1, 0, -5 ], renderOrder: 0 } ) );
	add( 'opaque_material_then_depth', s, c );
}
{	// A Group's renderOrder orders its whole subtree; a plain Object3D's does not.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const glass = material( 'transparent' );
	const g = new THREE.Group(); g.renderOrder = 2; s.add( g );
	const o = new THREE.Object3D(); o.renderOrder = 5; s.add( o );
	g.add( mesh( [ glass ], { position: [ 0, 0, -30 ], renderOrder: 0 } ) );
	o.add( mesh( [ glass ], { position: [ 0, 0, -40 ], renderOrder: 0 } ) );
	s.add( mesh( [ glass ], { position: [ 0, 0, -5 ], renderOrder: 3 } ) );
	const inner = new THREE.Group(); inner.renderOrder = -1; g.add( inner );
	inner.add( mesh( [ glass ], { position: [ 0, 0, -50 ], renderOrder: 0 } ) );
	add( 'group_order', s, c );
}
{	// Invisible parents hide their subtree; transmission goes to its own list.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const hidden = new THREE.Object3D(); hidden.visible = false; s.add( hidden );
	hidden.add( mesh( [ material( 'opaque' ) ], { renderOrder: 0 } ) );
	const glassy = material( 'transmissive' ); glassy.transparent = true;
	s.add( mesh( [ glassy ], { position: [ 0, 0, -8 ], renderOrder: 0 } ) );
	s.add( mesh( [ material( 'transmissive' ) ], { position: [ 0, 0, -4 ], renderOrder: 0 } ) );
	s.add( mesh( [ material( 'transparent' ) ], { position: [ 0, 0, -6 ], renderOrder: 0 } ) );
	add( 'hidden_subtree_and_transmission', s, c );
}
{	// Equal depth: the object id decides, in both lists.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const glass = material( 'transparent' ), wall = material( 'opaque' );
	for ( let i = 0; i < 3; i ++ ) { s.add( mesh( [ glass ], { position: [ 0, 0, -7 ], renderOrder: 0 } ) ); s.add( mesh( [ wall ], { position: [ 0, 0, -7 ], renderOrder: 0 } ) ); }
	s.children.reverse();
	add( 'ties_by_id', s, c );
}

// The rest of projectObject: hidden materials, multi-material meshes, sprites, lines, points, lights, nested groups.
{	// A material with visible = false is not drawn; a hidden material inside an array only drops its group.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const hidden = material( 'opaque' ); hidden.visible = false;
	s.add( mesh( [ hidden ], { position: [ 0, 0, -5 ], renderOrder: 0 } ) );
	const glass = material( 'transparent' ), wall = material( 'opaque' ), ghost = material( 'transparent' ); ghost.visible = false;
	const glass2 = material( 'transparent' );
	const multi = mesh( [], { material: [ wall, glass, ghost, glass2 ], position: [ 1, 0, -8 ], renderOrder: 0 } );
	multi.geometry.addGroup( 0, 6, 1 ); multi.geometry.addGroup( 6, 6, 0 ); multi.geometry.addGroup( 12, 6, 2 ); multi.geometry.addGroup( 18, 6, 7 );
	s.add( multi );
	s.add( mesh( [ glass ], { position: [ 0, 0, -12 ], renderOrder: 0 } ) );
	s.add( mesh( [ wall ], { position: [ -1, 0, -3 ], renderOrder: 0 } ) );
	add( 'hidden_materials_and_material_groups', s, c );
}
{	// A sprite's depth is its own position (no bounding sphere); lines and points sort like meshes; a light draws
	// nothing but its children do.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const label = new THREE.SpriteMaterial(); label.transparent = true;
	const sp = new THREE.Sprite( label ); sp.position.set( 0, 1, -9 ); sp.frustumCulled = false; s.add( sp );
	const off = new THREE.SpriteMaterial(); off.visible = false;
	const hiddenSprite = new THREE.Sprite( off ); hiddenSprite.position.set( 0, 2, -7 ); hiddenSprite.frustumCulled = false; s.add( hiddenSprite );
	const glass = material( 'transparent' );
	s.add( mesh( [ glass ], { position: [ 0, 0, -10 ], center: [ 0, 0, 3 ], renderOrder: 0 } ) );
	const lg = new THREE.BufferGeometry(); lg.boundingSphere = new THREE.Sphere( new THREE.Vector3( 0, 0, -2 ), 1 );
	const lm = new THREE.LineBasicMaterial( { transparent: true } );
	const line = new THREE.Line( lg, lm ); line.position.set( 2, 0, -6 ); line.frustumCulled = false; s.add( line );
	const pg = new THREE.BufferGeometry(); pg.boundingSphere = new THREE.Sphere( new THREE.Vector3( 0, 0, 0 ), 1 );
	const pts = new THREE.Points( pg, new THREE.PointsMaterial() ); pts.position.set( -2, 0, -4 ); pts.frustumCulled = false; s.add( pts );
	const sun = new THREE.DirectionalLight(); sun.position.set( 0, 5, -5 ); s.add( sun );
	sun.add( mesh( [ material( 'opaque' ) ], { position: [ 0, -5, -2 ], renderOrder: 0 } ) );
	add( 'sprites_lines_points_lights', s, c );
}
{	// A nested Group with renderOrder 0 sets groupOrder back to 0 for its subtree; a Group's own renderOrder is not an
	// item's renderOrder.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const glass = material( 'transparent' );
	const outer = new THREE.Group(); outer.renderOrder = 2; s.add( outer );
	const inner = new THREE.Group(); inner.renderOrder = 0; outer.add( inner );
	outer.add( mesh( [ glass ], { position: [ 0, 0, -20 ], renderOrder: 0 } ) );
	inner.add( mesh( [ glass ], { position: [ 0, 0, -30 ], renderOrder: 0 } ) );
	s.add( mesh( [ glass ], { position: [ 0, 0, -5 ], renderOrder: 1 } ) );
	add( 'nested_group_resets_order', s, c );
}

// Frustum culling and layers (WebGLRenderer.render builds the frustum from the same projection × view matrix).
{	// Culled: behind the camera, beside the view, beyond far; kept: a big sphere reaching in from outside, a scaled
	// object whose sphere only reaches in through its scale, and an object outside the view with frustumCulled off.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 100 );
	const glass = material( 'transparent' ), wall = material( 'opaque' );
	s.add( mesh( [ glass ], { position: [ 0, 0, 5 ], culled: true, renderOrder: 0 } ) );
	s.add( mesh( [ glass ], { position: [ 40, 0, -10 ], culled: true, renderOrder: 0 } ) );
	s.add( mesh( [ glass ], { position: [ 0, 0, -150 ], culled: true, renderOrder: 0 } ) );
	s.add( mesh( [ wall ], { position: [ 22, 0, -10 ], radius: 10, culled: true, renderOrder: 0 } ) );
	s.add( mesh( [ wall ], { position: [ 15, 0, -11 ], radius: 1, culled: true, renderOrder: 0 } ) );
	const scaled = mesh( [ wall ], { position: [ 15, 0, -10 ], radius: 1, culled: true, renderOrder: 0 } ); scaled.scale.set( 1, 6, 1 ); s.add( scaled );
	s.add( mesh( [ glass ], { position: [ -40, 0, -10 ], culled: false, renderOrder: 0 } ) );
	const label = new THREE.SpriteMaterial(); const sp = new THREE.Sprite( label ); sp.position.set( 18, 0, -10 ); s.add( sp );
	const sp2 = new THREE.Sprite( label ); sp2.position.set( 0, 0, -10 ); sp2.scale.set( 3, 3, 1 ); s.add( sp2 );
	const edge = new THREE.Sprite( label ); edge.position.set( 11.1, 0, -10 ); s.add( edge );   // 0.58 outside: kept by the 0.7071 radius
	const edge2 = new THREE.Sprite( label ); edge2.position.set( 11.45, 0, -10 ); s.add( edge2 ); // 0.83 outside: culled
	add( 'frustum_culling', s, c );
}
{	// Layers: an object on another layer is not drawn, but its children on the camera's layer are; enabling a layer on the
	// camera brings it in.
	const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 );
	const glass = material( 'transparent' );
	const hud = mesh( [ glass ], { position: [ 0, 0, -10 ], renderOrder: 0 } ); hud.layers.set( 2 ); s.add( hud );
	hud.add( mesh( [ glass ], { position: [ 0, 0, -5 ], renderOrder: 0 } ) );
	const both = mesh( [ glass ], { position: [ 1, 0, -12 ], renderOrder: 0 } ); both.layers.enable( 3 ); s.add( both );
	const grp = new THREE.Group(); grp.renderOrder = 5; grp.layers.set( 4 ); s.add( grp );
	grp.add( mesh( [ glass ], { position: [ 0, 1, -8 ], renderOrder: 0 } ) );
	add( 'layers_default_camera', s, c );
	const c2 = new THREE.PerspectiveCamera( 60, 16 / 9, 0.1, 500 ); c2.layers.enable( 2 );
	add( 'layers_camera_sees_two', s, c2 );
}

// Random scenes: nested groups and objects, shared materials, mixed render orders.
for ( let k = 0; k < 18; k ++ ) {
	const s = new THREE.Scene();
	const materials = [ material( 'opaque' ), material( 'opaque' ), material( 'opaque' ), material( 'transparent' ), material( 'transparent' ), material( 'transmissive' ) ];
	const hiddenMat = material( 'transparent' ); hiddenMat.visible = false;
	const spriteMat = new THREE.SpriteMaterial(), spriteMat2 = new THREE.SpriteMaterial( { transparent: false } );
	const parents = [ s ];
	const n = 6 + Math.floor( rnd() * 10 );
	for ( let i = 0; i < n; i ++ ) {
		const parent = pick( parents ); const r = rnd();
		if ( r < 0.15 ) { const g = new THREE.Group(); g.renderOrder = pick( [ 0, 1, 2, -1 ] ); g.position.set( r3( range( -2, 2 ) ), 0, r3( range( -4, 0 ) ) ); parent.add( g ); parents.push( g ); }
		else if ( r < 0.25 ) { const o = new THREE.Object3D(); o.renderOrder = pick( [ 0, 3 ] ); o.visible = rnd() > 0.2; o.rotation.y = r3( range( -1, 1 ) ); parent.add( o ); parents.push( o ); }
		else if ( r < 0.35 ) {
			const sp = new THREE.Sprite( pick( [ spriteMat, spriteMat2 ] ) ); sp.frustumCulled = false; sp.renderOrder = pick( [ 0, 0, 1 ] );
			sp.position.set( r3( range( -6, 6 ) ), r3( range( -2, 2 ) ), r3( range( -25, -3 ) ) ); parent.add( sp );
		} else if ( r < 0.45 ) {
			const m = mesh( materials, {} ); m.material = [ pick( materials ), pick( materials ), hiddenMat ];
			for ( const k of [ 0, 1, 2, 1 ] ) m.geometry.addGroup( 0, 3, k );
			parent.add( m );
		}
		else {
			const m = mesh( materials, { center: rnd() < 0.3 ? [ r3( range( -2, 2 ) ), 0, r3( range( -3, 3 ) ) ] : [ 0, 0, 0 ],
				radius: pick( [ 0.5, 1, 2, 4 ] ), culled: rnd() < 0.7,
				position: [ r3( range( -22, 22 ) ), r3( range( -6, 6 ) ), r3( range( -40, 3 ) ) ] } );
			m.visible = rnd() > 0.08;
			if ( rnd() < 0.12 ) m.layers.set( 2 );
			parent.add( m );
		}
	}
	const cam = camera(); if ( rnd() < 0.3 ) cam.layers.enable( 2 );
	add( `random_${String( k ).padStart( 2, '0' )}`, s, cam );
}

process.stdout.write( JSON.stringify( cases, null, 1 ) + '\n' );
