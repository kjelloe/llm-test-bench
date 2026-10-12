// Writes the test fixtures to stdout: three's own geometry code (js/three, three 0.165.0) run on each case.
// node js/make-fixtures.mjs > tests/FastengineTests/fixtures.json
import { BoxGeometry } from './three/BoxGeometry.js';
import { CylinderGeometry } from './three/CylinderGeometry.js';
import { ConeGeometry } from './three/ConeGeometry.js';
import { SphereGeometry } from './three/SphereGeometry.js';
import { TorusGeometry } from './three/TorusGeometry.js';

const PI = Math.PI;
const cases = [
	[ 'box_unit', 'Box', [ 1, 1, 1 ], () => new BoxGeometry( 1, 1, 1 ) ],
	[ 'box_segmented', 'Box', [ 2, 0.5, 3, 2, 1, 3 ], () => new BoxGeometry( 2, 0.5, 3, 2, 1, 3 ) ],
	[ 'cylinder_default', 'Cylinder', [ 1, 1, 1, 32, 1, false, 0, 2 * PI ], () => new CylinderGeometry() ],
	[ 'cylinder_five_sides', 'Cylinder', [ 0.3, 0.3, 2, 5, 1, false, 0, 2 * PI ], () => new CylinderGeometry( 0.3, 0.3, 2, 5 ) ],
	[ 'cylinder_tapered_open', 'Cylinder', [ 0.5, 1, 2, 7, 3, true, 0, 2 * PI ], () => new CylinderGeometry( 0.5, 1, 2, 7, 3, true ) ],
	[ 'cylinder_partial', 'Cylinder', [ 1, 1, 1, 6, 1, false, PI / 4, PI ], () => new CylinderGeometry( 1, 1, 1, 6, 1, false, PI / 4, PI ) ],
	[ 'cone_three_sides', 'Cone', [ 1, 2, 3, 1, false, 0, 2 * PI ], () => new ConeGeometry( 1, 2, 3 ) ],
	[ 'cone_open', 'Cone', [ 0.5, 1, 8, 2, true, 0, 2 * PI ], () => new ConeGeometry( 0.5, 1, 8, 2, true ) ],
	[ 'sphere_small', 'Sphere', [ 1, 8, 6, 0, 2 * PI, 0, PI ], () => new SphereGeometry( 1, 8, 6 ) ],
	[ 'sphere_hemisphere', 'Sphere', [ 2, 12, 4, 0, 2 * PI, 0, PI / 2 ], () => new SphereGeometry( 2, 12, 4, 0, 2 * PI, 0, PI / 2 ) ],
	[ 'sphere_band', 'Sphere', [ 1, 9, 5, PI / 3, PI, PI / 4, PI / 2 ], () => new SphereGeometry( 1, 9, 5, PI / 3, PI, PI / 4, PI / 2 ) ],
	[ 'torus_default', 'Torus', [ 1, 0.4, 12, 48, 2 * PI ], () => new TorusGeometry() ],
	[ 'torus_arc', 'Torus', [ 2, 0.25, 5, 7, PI ], () => new TorusGeometry( 2, 0.25, 5, 7, PI ) ],
];

const out = cases.map( ( [ name, kind, args, make ] ) => {
	const g = make();
	return {
		name, kind, args,
		positions: Array.from( g.attributes.position.array ),
		normals: Array.from( g.attributes.normal.array ),
		uvs: Array.from( g.attributes.uv.array ),
		indices: g.index,
	};
} );
process.stdout.write( JSON.stringify( out ) + '\n' );
