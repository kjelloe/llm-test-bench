namespace Fastengine
{
    // A browser three.js ShaderMaterial's GLSL as GLSL 330 for raylib (GL 3.3 core). The game's shaders are written for
    // three r162 (WebGL): three's built-in attribute and uniform names, gl_FragColor, precision lines, #include chunks.
    // Raylib's shader loader binds its own names: attributes vertexPosition, vertexTexCoord, vertexNormal (and
    // vertexColor, vertexTangent, vertexTexCoord2), uniforms matModel, matView, matProjection, mvp. The renderer sets a
    // uniform `cameraPosition` (world space) on every ported shader.
    public static class ShaderPort
    {
        public static string Vertex(string threeGlsl) => "#version 330\n" + threeGlsl;

        public static string Fragment(string threeGlsl) => "#version 330\n" + threeGlsl;
    }
}
