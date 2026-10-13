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
	( function projectObject( object, groupOrder ) {
		if ( object.visible === false ) return;
		if ( object.isGroup ) groupOrder = object.renderOrder;
		else if ( object.isMesh ) {
			v.copy( object.geometry.boundingSphere.center ).applyMatrix4( object.matrixWorld ).applyMatrix4( proj );
			const m = object.material;
			const item = { id: object.id, material: m, groupOrder, renderOrder: object.renderOrder, z: v.z };
			( m.transmission > 0 ? lists.transmissive : m.transparent === true ? lists.transparent : lists.opaque ).push( item );
		}
		for ( const child of object.children ) projectObject( child, groupOrder );
	} )( scene, 0 );
	lists.opaque.sort( painterSortStable );
	lists.transmissive.sort( reversePainterSortStable );
	lists.transparent.sort( reversePainterSortStable );
	return { proj, lists };
}

function node( o ) {
	const n = { id: o.id, kind: o.isGroup ? 'group' : o.isMesh ? 'mesh' : 'object', renderOrder: o.renderOrder, visible: o.visible,
		world: Array.from( o.matrixWorld.elements ) };
	if ( o.isMesh ) {
		const m = o.material;
		n.center = o.geometry.boundingSphere.center.toArray();
		n.material = { id: m.id, transparent: m.transparent, transmission: m.transmission };
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
	g.boundingSphere = new THREE.Sphere( new THREE.Vector3( ...( opts.center ?? [ 0, 0, 0 ] ) ), 1 );
	const o = new THREE.Mesh( g, opts.material ?? pick( materials ) );
	o.position.set( ...( opts.position ?? [ r3( range( -8, 8 ) ), r3( range( -3, 3 ) ), r3( range( -30, -2 ) ) ] ) );
	o.rotation.set( r3( range( -1, 1 ) ), r3( range( -3, 3 ) ), 0 );
	o.renderOrder = opts.renderOrder ?? pick( [ 0, 0, 0, 0, 1, -1 ] );
	o.frustumCulled = false;
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
	cases.push( { name, viewProjection: Array.from( proj.elements ), cameraPosition: cam.position.toArray(), scene: node( scene ),
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

// Random scenes: nested groups and objects, shared materials, mixed render orders.
for ( let k = 0; k < 18; k ++ ) {
	const s = new THREE.Scene();
	const materials = [ material( 'opaque' ), material( 'opaque' ), material( 'opaque' ), material( 'transparent' ), material( 'transparent' ), material( 'transmissive' ) ];
	const parents = [ s ];
	const n = 6 + Math.floor( rnd() * 10 );
	for ( let i = 0; i < n; i ++ ) {
		const parent = pick( parents ); const r = rnd();
		if ( r < 0.15 ) { const g = new THREE.Group(); g.renderOrder = pick( [ 0, 1, 2, -1 ] ); g.position.set( r3( range( -2, 2 ) ), 0, r3( range( -4, 0 ) ) ); parent.add( g ); parents.push( g ); }
		else if ( r < 0.25 ) { const o = new THREE.Object3D(); o.renderOrder = pick( [ 0, 3 ] ); o.visible = rnd() > 0.2; o.rotation.y = r3( range( -1, 1 ) ); parent.add( o ); parents.push( o ); }
		else { const m = mesh( materials, { center: rnd() < 0.3 ? [ r3( range( -2, 2 ) ), 0, r3( range( -3, 3 ) ) ] : [ 0, 0, 0 ] } ); m.visible = rnd() > 0.08; parent.add( m ); }
	}
	add( `random_${String( k ).padStart( 2, '0' )}`, s, camera() );
}

process.stdout.write( JSON.stringify( cases, null, 1 ) + '\n' );
