using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using Raylib_cs;

namespace Fastengine
{
    // three.js InstancedBufferGeometry for raylib: a base shape drawn `count` times in one draw call, each copy given its
    // own values of the material's per-instance attributes (InstancedBufferAttribute), with the browser's ShaderMaterial
    // GLSL unchanged. The scene runner draws the mesh Build returns with one Raylib.DrawMesh, using a shader made of
    // ShaderPort.WrapVertex(Instancing.Attributes(glsl)).
    // Reference: fastengine's InstancedBufferGeometry (Three/Geometry.cs), Renderer.Upload/WriteVertex (one mesh, the base
    // shape repeated, an attribute in raylib's spare tangent then texcoord2 slots, unrolled past raylib's 16-bit indices)
    // and Shaders.CustomAttributes, fastengine 6ae4ed8.
    public sealed record InstanceAttribute(string Name, int Size, float[] Values);

    public static class Instancing
    {
        // The base shape: positions (x, y, z per vertex), uvs (u, v per vertex) and triangle indices, as three's
        // BufferGeometry holds them. Each attribute holds Size values per instance, instance after instance.
        public static Mesh Build(float[] positions, float[] uvs, int[] indices, int count, params InstanceAttribute[] attributes)
        {
            if (attributes.Length > 2 || attributes.Length > 1 && attributes[1].Size > 2)
                throw new ArgumentException("raylib's spare slots hold one attribute of up to 4 values and one of up to 2");
            var nv = positions.Length / 3;
            // raylib indexes with ushort: past 65,535 vertices the copies go in as a plain triangle list.
            var unrolled = nv * count > ushort.MaxValue;
            var vertices = unrolled ? indices.Length * count : nv * count;
            var mesh = new Mesh { VertexCount = vertices, TriangleCount = indices.Length / 3 * count };
            mesh.AllocVertices();
            mesh.AllocTexCoords();
            if (!unrolled) mesh.AllocIndices();
            if (attributes.Length > 0) mesh.AllocTangents();
            if (attributes.Length > 1) mesh.AllocTexCoords2();
            unsafe
            {
                for (var k = 0; k < count; k++)
                {
                    var per = unrolled ? indices.Length : nv;
                    for (var j = 0; j < per; j++)
                    {
                        var v = k * per + j;
                        var i = unrolled ? indices[j] : j;
                        for (var c = 0; c < 3; c++) mesh.Vertices[v * 3 + c] = positions[i * 3 + c];
                        for (var c = 0; c < 2; c++) mesh.TexCoords[v * 2 + c] = uvs[i * 2 + c];
                        if (attributes.Length > 0)
                        {
                            var a = attributes[0];
                            for (var c = 0; c < 4; c++) mesh.Tangents[v * 4 + c] = c < a.Size ? a.Values[k * a.Size + c] : 0;
                        }
                        if (attributes.Length > 1)
                        {
                            var a = attributes[1];
                            for (var c = 0; c < 2; c++) mesh.TexCoords2[v * 2 + c] = c < a.Size ? a.Values[k * a.Size + c] : 0;
                        }
                    }
                    if (!unrolled)
                        for (var i = 0; i < indices.Length; i++) mesh.Indices[k * indices.Length + i] = (ushort)(k * nv + indices[i]);
                }
            }
            Raylib.UploadMesh(ref mesh, false);
            return mesh;
        }

        // The browser's vertex shader, made to read the per-instance attributes from where Build put them: in
        // declaration order, raylib's tangent slot, then texcoord2.
        public static string Attributes(string glsl)
        {
            var slot = 0;
            return Regex.Replace(glsl, @"^\s*attribute\s+(float|vec2|vec3|vec4)\s+(\w+)\s*;", m =>
            {
                var size = m.Groups[1].Value switch { "float" => 1, "vec2" => 2, "vec3" => 3, _ => 4 };
                var swizzle = "xyzw"[..size];
                return slot++ == 0
                    ? $"in vec4 vertexTangent;\n#define {m.Groups[2].Value} vertexTangent.{swizzle}"
                    : $"in vec2 vertexTexCoord2;\n#define {m.Groups[2].Value} vertexTexCoord2.{swizzle}";
            }, RegexOptions.Multiline);
        }
    }
}
