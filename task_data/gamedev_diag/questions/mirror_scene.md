# mirror_scene

A three.js scene (z pointing south) is mirrored into Unity (z pointing north) by negating the z of every position. What else has to change?

A. Rotations about z change sign, those about x and y keep theirs, and copied index buffers keep the winding three.js gave them.
B. Rotations about x and y change sign, those about z keep theirs, and copied index buffers need reversed winding.
C. Nothing else: Unity converts handedness itself when a mesh or rotation is assigned from script.
D. All three rotation angles change sign, and copied index buffers keep their winding unchanged.
E. y and z must also be swapped, because Unity is y-up, and every rotation angle changes sign as well.
