# winding_not_lighting

After CarrierDominion's island meshes are mirrored into Unity (z negated), the islands render dark, and from above you can see the inside of the far slopes. A pixel sampled on a sunlit near slope matches the colour computed by hand from the same light and normal, and it matches the browser. What is wrong, and what is the fix?

A. The normals point inward after negating z; negate each normal's z and recalculate the tangents and bounds so the lighting matches the browser again.
B. The directional light was not mirrored, so it lights the hidden side; negate the z of its direction and the slopes light up again.
C. The winding was not reversed with the mirror, so Unity culls the outer faces; reverse each triangle's index order and keep the lighting.
D. The shadow bias is too large for the mirrored scale and every slope shadows itself; lower the main light's depth and normal bias.
E. The importer set the material's Render Face to Back; set it to Both so the outer faces draw as well.
