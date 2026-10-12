// Minimal stand-ins for the three.js classes the geometry files import, so that three's own geometry code
// (copied unchanged from three 0.165.0, MIT, see LICENSE) runs under Node without the whole library.
export class Vector2 {
	constructor( x = 0, y = 0 ) { this.x = x; this.y = y; }
}
export class Vector3 {
	constructor( x = 0, y = 0, z = 0 ) { this.x = x; this.y = y; this.z = z; }
	set( x, y, z ) { this.x = x; this.y = y; this.z = z; return this; }
	copy( v ) { this.x = v.x; this.y = v.y; this.z = v.z; return this; }
	add( v ) { this.x += v.x; this.y += v.y; this.z += v.z; return this; }
	sub( v ) { this.x -= v.x; this.y -= v.y; this.z -= v.z; return this; }
	subVectors( a, b ) { this.x = a.x - b.x; this.y = a.y - b.y; this.z = a.z - b.z; return this; }
	multiplyScalar( s ) { this.x *= s; this.y *= s; this.z *= s; return this; }
	length() { return Math.sqrt( this.x * this.x + this.y * this.y + this.z * this.z ); }
	normalize() { return this.multiplyScalar( 1 / ( this.length() || 1 ) ); }
}
export class Float32BufferAttribute {
	constructor( array, itemSize ) { this.array = new Float32Array( array ); this.itemSize = itemSize; }
}
export class BufferGeometry {
	constructor() { this.attributes = {}; this.index = null; this.groups = []; }
	setIndex( index ) { this.index = index; }
	setAttribute( name, attribute ) { this.attributes[ name ] = attribute; }
	addGroup( start, count, materialIndex ) { this.groups.push( { start, count, materialIndex } ); }
	copy( source ) { return this; }
}
