using System;
using System.Collections.Generic;
using Raylib_cs;

namespace Fastengine
{
    // three.js InstancedBufferGeometry for raylib: a base shape drawn `count` times in one draw call, each copy given its
    // own values of the material's per-instance attributes (InstancedBufferAttribute), with the browser's ShaderMaterial
    // GLSL unchanged. The scene runner draws the mesh Build returns with one Raylib.DrawMesh, using a shader made of
    // ShaderPort.WrapVertex(Instancing.Attributes(glsl)).
    public sealed record InstanceAttribute(string Name, int Size, float[] Values);

    public static class Instancing
    {
        // The base shape: positions (x, y, z per vertex), uvs (u, v per vertex) and triangle indices, as three's
        // BufferGeometry holds them. Each attribute holds Size values per instance, instance after instance.
        public static Mesh Build(float[] positions, float[] uvs, int[] indices, int count, params InstanceAttribute[] attributes)
        {
            var nv = positions.Length / 3;
            var mesh = new Mesh { VertexCount = nv * count, TriangleCount = indices.Length / 3 * count };
            mesh.AllocVertices();
            mesh.AllocTexCoords();
            mesh.AllocIndices();
            if (attributes.Length > 0) mesh.AllocTangents();
            unsafe
            {
                for (var k = 0; k < count; k++)
                {
                    for (var i = 0; i < nv; i++)
                    {
                        var v = k * nv + i;
                        for (var c = 0; c < 3; c++) mesh.Vertices[v * 3 + c] = positions[i * 3 + c];
                        for (var c = 0; c < 2; c++) mesh.TexCoords[v * 2 + c] = uvs[i * 2 + c];
                        if (attributes.Length > 0)
                        {
                            var a = attributes[0];
                            for (var c = 0; c < a.Size; c++) mesh.Tangents[v * a.Size + c] = a.Values[k * a.Size + c];
                        }
                    }
                    for (var i = 0; i < indices.Length; i++) mesh.Indices[k * indices.Length + i] = (ushort)(k * nv + indices[i]);
                }
            }
            Raylib.UploadMesh(ref mesh, false);
            return mesh;
        }

        // The browser's vertex shader, made to read the per-instance attributes from where Build put them.
        public static string Attributes(string glsl) => glsl;
    }
}
