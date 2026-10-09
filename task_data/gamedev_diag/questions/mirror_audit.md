# mirror_audit

A three.js ship is ported to Unity by mirroring z (Unity z = -three z): positions get z negated, rotations about x and y are negated, and every primitive mesh is built in Unity with three.js's own vertex formulas (cylinder vertex k at angle 2*PI*k/N as (r*sin, y, r*cos)). Screens match the browser, except some parts. Which parts are still wrong, and how are they fixed?

A. Every box, because the z mirror reverses its face winding in Unity; reverse each box's triangle order when building it.
B. Cylinders with an even side count, whose first vertex lands on the mirrored side; turn them by one facet.
C. Only parts rotated about z, because the mirror also negates rotations about z; negate those angles.
D. Cylinders and cones with an odd side count are mirrored about their own axis; turn each 180 degrees about it.
E. Spheres, because their UV seam ends up on the other side of the part; rotate each 180 degrees about y.
