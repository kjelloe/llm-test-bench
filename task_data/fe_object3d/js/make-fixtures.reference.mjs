// Writes the test fixtures to stdout: scene graphs built with three r162's own Object3D and PerspectiveCamera
// (js/three.reference.mjs), lookAt calls applied in order, then every node's matrixWorld.
// node js/make-fixtures.reference.mjs > tests/FastengineTests/fixtures.json
import * as THREE from './three.reference.mjs';

let seed = 7338;
function rnd() { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul( seed ^ seed >>> 15, 1 | seed ); t = t + Math.imul( t ^ t >>> 7, 61 | t ) ^ t; return ( ( t ^ t >>> 14 ) >>> 0 ) / 4294967296; }
const range = ( lo, hi ) => Math.round( ( lo + ( hi - lo ) * rnd() ) * 1000 ) / 1000;

function make( kind, p, r, s ) {
	const o = kind === 'camera' ? new THREE.PerspectiveCamera( 60, 1.5, 0.1, 100 ) : new THREE.Object3D();
	o.position.set( ...p ); o.rotation.set( ...r ); o.scale.set( ...s );
	return o;
}

function describe( o ) {
	return { id: o.id, kind: o.isCamera ? 'camera' : 'object', position: o.position.toArray(),
		rotation: [ o.rotation.x, o.rotation.y, o.rotation.z ], scale: o.scale.toArray(), children: o.children.map( describe ) };
}

const cases = [];
// build() returns the root; looks are [object, [x, y, z]] pairs applied in order after the tree is described.
function add( name, build ) {
	const looks = [];
	const root = build( ( o, t ) => looks.push( [ o, t ] ) );
	const tree = describe( root );
	for ( const [ o, t ] of looks ) o.lookAt( new THREE.Vector3( ...t ) );
	root.updateMatrixWorld( true );
	const world = {};
	root.traverse( ( o ) => { world[ o.id ] = Array.from( o.matrixWorld.elements ); } );
	cases.push( { name, tree, looks: looks.map( ( [ o, t ] ) => ( { id: o.id, target: t } ) ), world } );
}

add( 'nested_world_matrices', () => {
	const a = make( 'object', [ 1, 2, 3 ], [ 0.3, -0.5, 0.2 ], [ 1, 2, 0.5 ] );
	const b = a.add( make( 'object', [ -2, 0.5, 1 ], [ 1.1, 0.4, -0.7 ], [ 0.5, 0.5, 3 ] ) ).children[ 0 ];
	b.add( make( 'object', [ 0, 1, -1 ], [ 0, 2.5, 0 ], [ 2, 1, 1 ] ) );
	return a;
} );
add( 'object_faces_target_with_plus_z', ( look ) => {
	const root = make( 'object', [ 0, 0, 0 ], [ 0, 0, 0 ], [ 1, 1, 1 ] );
	const o = root.add( make( 'object', [ 1, 1, 1 ], [ 0.4, 0.4, 0.4 ], [ 1, 1, 1 ] ) ).children[ 0 ];
	o.add( make( 'object', [ 0, 0, 2 ], [ 0, 0, 0 ], [ 1, 1, 1 ] ) );
	look( o, [ 5, 2, -4 ] );
	return root;
} );
add( 'camera_faces_target_with_minus_z', ( look ) => {
	const root = make( 'object', [ 0, 0, 0 ], [ 0, 0, 0 ], [ 1, 1, 1 ] );
	const c = root.add( make( 'camera', [ 3, 4, 10 ], [ 0, 0, 0 ], [ 1, 1, 1 ] ) ).children[ 0 ];
	c.add( make( 'object', [ 0, 0, -3 ], [ 0, 0, 0 ], [ 1, 1, 1 ] ) );
	look( c, [ 0, 0, 0 ] );
	return root;
} );
add( 'look_inside_rotated_parent', ( look ) => {
	const root = make( 'object', [ 2, -1, 0 ], [ 0.5, 1.2, -0.3 ], [ 2, 2, 2 ] );
	const o = root.add( make( 'object', [ 1, 0, 0 ], [ 0, 0, 0 ], [ 1, 3, 1 ] ) ).children[ 0 ];
	look( o, [ -3, 5, 2 ] );
	return root;
} );
add( 'look_straight_down', ( look ) => {
	const root = make( 'object', [ 0, 0, 0 ], [ 0, 0, 0 ], [ 1, 1, 1 ] );
	const o = root.add( make( 'object', [ 2, 10, -1 ], [ 0, 0, 0 ], [ 1, 1, 1 ] ) ).children[ 0 ];
	const c = root.add( make( 'camera', [ -2, 10, 1 ], [ 0, 0, 0 ], [ 1, 1, 1 ] ) ).children[ 1 ];
	look( o, [ 2, 0, -1 ] );
	look( c, [ -2, -5, 1 ] );
	return root;
} );
add( 'look_at_own_position', ( look ) => {
	const root = make( 'object', [ 0, 0, 0 ], [ 0, 0, 0 ], [ 1, 1, 1 ] );
	const o = root.add( make( 'object', [ 1, 2, 3 ], [ 0.7, 0, 0 ], [ 1, 1, 1 ] ) ).children[ 0 ];
	look( o, [ 1, 2, 3 ] );
	return root;
} );
add( 'parent_then_child_look', ( look ) => {
	const root = make( 'object', [ 0, 0, 0 ], [ 0, 0, 0 ], [ 1, 1, 1 ] );
	const p = root.add( make( 'object', [ 0, 1, 0 ], [ 0, 0, 0 ], [ 1, 1, 1 ] ) ).children[ 0 ];
	const c = p.add( make( 'camera', [ 0, 2, 5 ], [ 0, 0, 0 ], [ 1, 1, 1 ] ) ).children[ 0 ];
	look( p, [ 10, 1, 0 ] );
	look( c, [ 0, 0, 0 ] );
	return root;
} );

for ( let k = 0; k < 12; k ++ ) add( `random_${String( k ).padStart( 2, '0' )}`, ( look ) => {
	const root = make( 'object', [ range( -3, 3 ), range( -3, 3 ), range( -3, 3 ) ], [ range( -1, 1 ), range( -3, 3 ), range( -1, 1 ) ], [ 1.5, 1.5, 1.5 ] );
	const uniform = [ root ];
	const all = [ root ];
	for ( let i = 0; i < 7; i ++ ) {
		const s = rnd() < 0.5 ? range( 0.5, 2 ) : null;
		const parent = rnd() < 0.6 ? uniform[ Math.floor( rnd() * uniform.length ) ] : all[ Math.floor( rnd() * all.length ) ];
		const o = make( rnd() < 0.25 ? 'camera' : 'object', [ range( -4, 4 ), range( -4, 4 ), range( -4, 4 ) ],
			[ range( -1.5, 1.5 ), range( -3, 3 ), range( -1.5, 1.5 ) ], s ? [ s, s, s ] : [ range( 0.5, 2 ), range( 0.5, 2 ), range( 0.5, 2 ) ] );
		parent.add( o ); all.push( o );
		if ( s ) uniform.push( o );
		// lookAt only below parents with uniform scale (three does not support non-uniformly scaled parents)
		let ok = true; for ( let q = o.parent; q; q = q.parent ) if ( q.scale.x !== q.scale.y || q.scale.y !== q.scale.z ) ok = false;
		if ( ok && rnd() < 0.5 ) look( o, [ range( -10, 10 ), range( -10, 10 ), range( -10, 10 ) ] );
	}
	return root;
} );

process.stdout.write( JSON.stringify( cases, null, 1 ) + '\n' );
