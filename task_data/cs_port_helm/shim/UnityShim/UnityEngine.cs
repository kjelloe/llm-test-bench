// Minimal stand-in for the UnityEngine API, so Unity-style client code can be
// compiled and unit-tested with plain `dotnet test` (no Unity Editor).
// ONLY the members below exist. Anything else from UnityEngine (Time, JsonUtility,
// eulerAngles, AddComponent, Destroy, ...) is NOT available.
// Semantics follow Unity: Vector3/Quaternion == are approximate, Quaternion.Euler
// applies Z, then X, then Y (degrees), Unity's coordinate system is left-handed, Y-up.
using System;
using System.Collections.Generic;

namespace UnityEngine
{
    public static class Mathf
    {
        public const float PI = (float)Math.PI;
        public const float Deg2Rad = PI / 180f;
        public const float Rad2Deg = 180f / PI;
        public const float Epsilon = 1.401298E-45f;
        public const float Infinity = float.PositiveInfinity;

        public static float Abs(float f) => Math.Abs(f);
        public static int Abs(int v) => Math.Abs(v);
        public static float Min(float a, float b) => a < b ? a : b;
        public static float Max(float a, float b) => a > b ? a : b;
        public static int Min(int a, int b) => a < b ? a : b;
        public static int Max(int a, int b) => a > b ? a : b;
        public static float Sqrt(float f) => (float)Math.Sqrt(f);
        public static float Pow(float f, float p) => (float)Math.Pow(f, p);
        public static float Tan(float f) => (float)Math.Tan(f);
        public static float Asin(float f) => (float)Math.Asin(f);
        public static float Atan(float f) => (float)Math.Atan(f);
        public static float Ceil(float f) => (float)Math.Ceiling(f);
        public static int CeilToInt(float f) => (int)Math.Ceiling(f);

        // Unity's sRGB transfer curve (and a 2.2 power above 1).
        public static float GammaToLinearSpace(float value) =>
            value <= 0.04045f ? value / 12.92f : value < 1f ? (float)Math.Pow((value + 0.055f) / 1.055f, 2.4f) : (float)Math.Pow(value, 2.2f);
        public static float LinearToGammaSpace(float value) =>
            value <= 0f ? 0f : value <= 0.0031308f ? 12.92f * value : value < 1f ? 1.055f * (float)Math.Pow(value, 0.4166667f) - 0.055f : (float)Math.Pow(value, 0.45454545f);
        public static float Sin(float f) => (float)Math.Sin(f);
        public static float Cos(float f) => (float)Math.Cos(f);
        public static float Acos(float f) => (float)Math.Acos(f);
        public static float Atan2(float y, float x) => (float)Math.Atan2(y, x);
        public static float Sign(float f) => f >= 0f ? 1f : -1f;
        public static float Floor(float f) => (float)Math.Floor(f);
        public static float Round(float f) => (float)Math.Round(f);
        public static int RoundToInt(float f) => (int)Math.Round(f);
        public static int FloorToInt(float f) => (int)Math.Floor(f);

        public static float Clamp(float value, float min, float max) =>
            value < min ? min : value > max ? max : value;
        public static int Clamp(int value, int min, int max) =>
            value < min ? min : value > max ? max : value;
        public static float Clamp01(float value) => Clamp(value, 0f, 1f);

        public static float Lerp(float a, float b, float t) => a + (b - a) * Clamp01(t);
        public static float LerpUnclamped(float a, float b, float t) => a + (b - a) * t;
        public static float InverseLerp(float a, float b, float value) =>
            a != b ? Clamp01((value - a) / (b - a)) : 0f;

        public static float MoveTowards(float current, float target, float maxDelta) =>
            Abs(target - current) <= maxDelta ? target : current + Sign(target - current) * maxDelta;

        // Result is in [0, length).
        public static float Repeat(float t, float length) =>
            Clamp(t - Floor(t / length) * length, 0f, length);

        public static bool Approximately(float a, float b) =>
            Abs(b - a) < Max(1E-06f * Max(Abs(a), Abs(b)), Epsilon * 8f);
    }

    public struct Vector2 : IEquatable<Vector2>
    {
        public float x;
        public float y;

        public Vector2(float x, float y) { this.x = x; this.y = y; }

        public static Vector2 zero => new Vector2(0f, 0f);
        public float magnitude => Mathf.Sqrt(x * x + y * y);

        public static Vector2 operator +(Vector2 a, Vector2 b) => new Vector2(a.x + b.x, a.y + b.y);
        public static Vector2 operator -(Vector2 a, Vector2 b) => new Vector2(a.x - b.x, a.y - b.y);
        public static Vector2 operator *(Vector2 a, float d) => new Vector2(a.x * d, a.y * d);
        public static Vector2 Lerp(Vector2 a, Vector2 b, float t)
        {
            t = Mathf.Clamp01(t);
            return new Vector2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t);
        }

        public bool Equals(Vector2 other) => x == other.x && y == other.y;
        public override bool Equals(object obj) => obj is Vector2 v && Equals(v);
        public override int GetHashCode() => HashCode.Combine(x, y);
        public override string ToString() => $"({x:F2}, {y:F2})";
    }

    public struct Vector3 : IEquatable<Vector3>
    {
        public const float kEpsilon = 1E-05f;
        public float x;
        public float y;
        public float z;

        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }

        public static Vector3 zero => new Vector3(0f, 0f, 0f);
        public static Vector3 one => new Vector3(1f, 1f, 1f);
        public static Vector3 up => new Vector3(0f, 1f, 0f);
        public static Vector3 down => new Vector3(0f, -1f, 0f);
        public static Vector3 right => new Vector3(1f, 0f, 0f);
        public static Vector3 left => new Vector3(-1f, 0f, 0f);
        public static Vector3 forward => new Vector3(0f, 0f, 1f);
        public static Vector3 back => new Vector3(0f, 0f, -1f);

        public float sqrMagnitude => x * x + y * y + z * z;
        public float magnitude => Mathf.Sqrt(sqrMagnitude);
        public Vector3 normalized
        {
            get
            {
                float m = magnitude;
                return m > kEpsilon ? this / m : zero;
            }
        }

        public static Vector3 operator +(Vector3 a, Vector3 b) => new Vector3(a.x + b.x, a.y + b.y, a.z + b.z);
        public static Vector3 operator -(Vector3 a, Vector3 b) => new Vector3(a.x - b.x, a.y - b.y, a.z - b.z);
        public static Vector3 operator -(Vector3 a) => new Vector3(-a.x, -a.y, -a.z);
        public static Vector3 operator *(Vector3 a, float d) => new Vector3(a.x * d, a.y * d, a.z * d);
        public static Vector3 operator *(float d, Vector3 a) => new Vector3(a.x * d, a.y * d, a.z * d);
        public static Vector3 operator /(Vector3 a, float d) => new Vector3(a.x / d, a.y / d, a.z / d);

        public static bool operator ==(Vector3 a, Vector3 b) => (a - b).sqrMagnitude < kEpsilon * kEpsilon;
        public static bool operator !=(Vector3 a, Vector3 b) => !(a == b);

        public static float Dot(Vector3 a, Vector3 b) => a.x * b.x + a.y * b.y + a.z * b.z;
        public static Vector3 Cross(Vector3 a, Vector3 b) =>
            new Vector3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
        public static float Distance(Vector3 a, Vector3 b) => (a - b).magnitude;
        public static Vector3 Scale(Vector3 a, Vector3 b) => new Vector3(a.x * b.x, a.y * b.y, a.z * b.z);
        public static Vector3 Lerp(Vector3 a, Vector3 b, float t) => LerpUnclamped(a, b, Mathf.Clamp01(t));
        public static Vector3 LerpUnclamped(Vector3 a, Vector3 b, float t) =>
            new Vector3(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t);
        public static Vector3 MoveTowards(Vector3 current, Vector3 target, float maxDistanceDelta)
        {
            Vector3 d = target - current;
            float dist = d.magnitude;
            return dist <= maxDistanceDelta || dist == 0f ? target : current + d / dist * maxDistanceDelta;
        }
        public static Vector3 ClampMagnitude(Vector3 v, float maxLength) =>
            v.sqrMagnitude > maxLength * maxLength ? v.normalized * maxLength : v;

        public bool Equals(Vector3 other) => x == other.x && y == other.y && z == other.z;
        public override bool Equals(object obj) => obj is Vector3 v && Equals(v);
        public override int GetHashCode() => HashCode.Combine(x, y, z);
        public override string ToString() => $"({x:F2}, {y:F2}, {z:F2})";
    }

    public struct Quaternion : IEquatable<Quaternion>
    {
        public const float kEpsilon = 1E-06f;
        public float x;
        public float y;
        public float z;
        public float w;

        public Quaternion(float x, float y, float z, float w) { this.x = x; this.y = y; this.z = z; this.w = w; }

        public static Quaternion identity => new Quaternion(0f, 0f, 0f, 1f);

        public Quaternion normalized
        {
            get
            {
                float m = Mathf.Sqrt(Dot(this, this));
                return m < Mathf.Epsilon ? identity : new Quaternion(x / m, y / m, z / m, w / m);
            }
        }

        public static Quaternion operator *(Quaternion a, Quaternion b) => new Quaternion(
            a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
            a.w * b.y + a.y * b.w + a.z * b.x - a.x * b.z,
            a.w * b.z + a.z * b.w + a.x * b.y - a.y * b.x,
            a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z);

        public static Vector3 operator *(Quaternion q, Vector3 v)
        {
            var u = new Vector3(q.x, q.y, q.z);
            Vector3 t = 2f * Vector3.Cross(u, v);
            return v + q.w * t + Vector3.Cross(u, t);
        }

        // Same rotation (q and -q) compare equal, as in Unity.
        public static bool operator ==(Quaternion a, Quaternion b) => Dot(a, b) > 1f - kEpsilon;
        public static bool operator !=(Quaternion a, Quaternion b) => !(a == b);

        public static float Dot(Quaternion a, Quaternion b) => a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w;

        public static float Angle(Quaternion a, Quaternion b)
        {
            float d = Mathf.Min(Mathf.Abs(Dot(a, b)), 1f);
            return d > 1f - kEpsilon ? 0f : Mathf.Acos(d) * 2f * Mathf.Rad2Deg;
        }

        public static Quaternion Inverse(Quaternion q)
        {
            float n = Dot(q, q);
            return new Quaternion(-q.x / n, -q.y / n, -q.z / n, q.w / n);
        }

        public static Quaternion AngleAxis(float angle, Vector3 axis)
        {
            Vector3 a = axis.normalized;
            float half = angle * Mathf.Deg2Rad * 0.5f;
            float s = Mathf.Sin(half);
            return new Quaternion(a.x * s, a.y * s, a.z * s, Mathf.Cos(half));
        }

        public static Quaternion Euler(float x, float y, float z) =>
            AngleAxis(y, Vector3.up) * AngleAxis(x, Vector3.right) * AngleAxis(z, Vector3.forward);
        public static Quaternion Euler(Vector3 euler) => Euler(euler.x, euler.y, euler.z);

        public static Quaternion LookRotation(Vector3 forward) => LookRotation(forward, Vector3.up);
        public static Quaternion LookRotation(Vector3 forward, Vector3 upwards)
        {
            Vector3 z = forward.normalized;
            Vector3 x = Vector3.Cross(upwards, z).normalized;
            if (x.sqrMagnitude < 1e-12f) return FromToRotation(Vector3.forward, z);
            Vector3 y = Vector3.Cross(z, x);
            float trace = x.x + y.y + z.z;
            Quaternion q;
            if (trace > 0f)
            {
                float s = Mathf.Sqrt(trace + 1f) * 2f;
                q = new Quaternion((y.z - z.y) / s, (z.x - x.z) / s, (x.y - y.x) / s, 0.25f * s);
            }
            else if (x.x > y.y && x.x > z.z)
            {
                float s = Mathf.Sqrt(1f + x.x - y.y - z.z) * 2f;
                q = new Quaternion(0.25f * s, (y.x + x.y) / s, (z.x + x.z) / s, (y.z - z.y) / s);
            }
            else if (y.y > z.z)
            {
                float s = Mathf.Sqrt(1f + y.y - x.x - z.z) * 2f;
                q = new Quaternion((y.x + x.y) / s, 0.25f * s, (z.y + y.z) / s, (z.x - x.z) / s);
            }
            else
            {
                float s = Mathf.Sqrt(1f + z.z - x.x - y.y) * 2f;
                q = new Quaternion((z.x + x.z) / s, (z.y + y.z) / s, 0.25f * s, (x.y - y.x) / s);
            }
            return q.normalized;
        }

        public static Quaternion FromToRotation(Vector3 from, Vector3 to)
        {
            Vector3 a = from.normalized, b = to.normalized;
            float d = Vector3.Dot(a, b);
            if (d < -0.999999f)
            {
                Vector3 axis = Vector3.Cross(Vector3.right, a);
                if (axis.sqrMagnitude < 1e-6f) axis = Vector3.Cross(Vector3.up, a);
                return AngleAxis(180f, axis);
            }
            Vector3 c = Vector3.Cross(a, b);
            return new Quaternion(c.x, c.y, c.z, 1f + d).normalized;
        }

        public static Quaternion Lerp(Quaternion a, Quaternion b, float t) => LerpUnclamped(a, b, Mathf.Clamp01(t));
        public static Quaternion LerpUnclamped(Quaternion a, Quaternion b, float t)
        {
            if (Dot(a, b) < 0f) b = new Quaternion(-b.x, -b.y, -b.z, -b.w);
            return new Quaternion(
                a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t,
                a.z + (b.z - a.z) * t, a.w + (b.w - a.w) * t).normalized;
        }

        public static Quaternion Slerp(Quaternion a, Quaternion b, float t) => SlerpUnclamped(a, b, Mathf.Clamp01(t));
        public static Quaternion SlerpUnclamped(Quaternion a, Quaternion b, float t)
        {
            float d = Dot(a, b);
            if (d < 0f) { b = new Quaternion(-b.x, -b.y, -b.z, -b.w); d = -d; }
            if (d > 0.9995f) return LerpUnclamped(a, b, t);
            float theta = Mathf.Acos(d);
            float sa = Mathf.Sin((1f - t) * theta) / Mathf.Sin(theta);
            float sb = Mathf.Sin(t * theta) / Mathf.Sin(theta);
            return new Quaternion(
                a.x * sa + b.x * sb, a.y * sa + b.y * sb,
                a.z * sa + b.z * sb, a.w * sa + b.w * sb).normalized;
        }

        public bool Equals(Quaternion other) => x == other.x && y == other.y && z == other.z && w == other.w;
        public override bool Equals(object obj) => obj is Quaternion q && Equals(q);
        public override int GetHashCode() => HashCode.Combine(x, y, z, w);
        public override string ToString() => $"({x:F5}, {y:F5}, {z:F5}, {w:F5})";
    }

    public struct Color : IEquatable<Color>
    {
        public float r, g, b, a;
        public Color(float r, float g, float b, float a) { this.r = r; this.g = g; this.b = b; this.a = a; }
        public Color(float r, float g, float b) : this(r, g, b, 1f) { }

        public static Color white => new Color(1f, 1f, 1f, 1f);
        public static Color black => new Color(0f, 0f, 0f, 1f);
        public static Color clear => new Color(0f, 0f, 0f, 0f);

        // sRGB-to-linear and back per channel; alpha is unchanged.
        public Color linear => new Color(Mathf.GammaToLinearSpace(r), Mathf.GammaToLinearSpace(g), Mathf.GammaToLinearSpace(b), a);
        public Color gamma => new Color(Mathf.LinearToGammaSpace(r), Mathf.LinearToGammaSpace(g), Mathf.LinearToGammaSpace(b), a);
        public float maxColorComponent => Math.Max(r, Math.Max(g, b));

        public static Color operator +(Color x, Color y) => new Color(x.r + y.r, x.g + y.g, x.b + y.b, x.a + y.a);
        public static Color operator -(Color x, Color y) => new Color(x.r - y.r, x.g - y.g, x.b - y.b, x.a - y.a);
        public static Color operator *(Color x, Color y) => new Color(x.r * y.r, x.g * y.g, x.b * y.b, x.a * y.a);
        public static Color operator *(Color c, float f) => new Color(c.r * f, c.g * f, c.b * f, c.a * f);
        public static Color operator *(float f, Color c) => c * f;
        public static Color operator /(Color c, float f) => new Color(c.r / f, c.g / f, c.b / f, c.a / f);
        public static bool operator ==(Color x, Color y) =>
            Math.Abs(x.r - y.r) < 1e-5f && Math.Abs(x.g - y.g) < 1e-5f && Math.Abs(x.b - y.b) < 1e-5f && Math.Abs(x.a - y.a) < 1e-5f;
        public static bool operator !=(Color x, Color y) => !(x == y);
        public static Color Lerp(Color x, Color y, float t) { t = Mathf.Clamp01(t); return x + (y - x) * t; }

        public static implicit operator Color(Color32 c) => new Color(c.r / 255f, c.g / 255f, c.b / 255f, c.a / 255f);

        public bool Equals(Color other) => r == other.r && g == other.g && b == other.b && a == other.a;
        public override bool Equals(object obj) => obj is Color c && Equals(c);
        public override int GetHashCode() => HashCode.Combine(r, g, b, a);
        public override string ToString() => $"RGBA({r:F3}, {g:F3}, {b:F3}, {a:F3})";
    }

    public struct Color32
    {
        public byte r, g, b, a;
        public Color32(byte r, byte g, byte b, byte a) { this.r = r; this.g = g; this.b = b; this.a = a; }

        public static implicit operator Color32(Color c) => new Color32(
            (byte)Math.Round(Mathf.Clamp01(c.r) * 255f), (byte)Math.Round(Mathf.Clamp01(c.g) * 255f),
            (byte)Math.Round(Mathf.Clamp01(c.b) * 255f), (byte)Math.Round(Mathf.Clamp01(c.a) * 255f));

        public override string ToString() => $"RGBA({r}, {g}, {b}, {a})";
    }

    public struct Bounds
    {
        public Vector3 center, size;
        public Bounds(Vector3 center, Vector3 size) { this.center = center; this.size = size; }
        public Vector3 extents => size * 0.5f;
        public Vector3 min => center - extents;
        public Vector3 max => center + extents;
    }

    // Vertices, triangles (three indices per triangle; a triangle's front face is the side its
    // vertices appear CLOCKWISE from, as in Unity) and per-vertex normals.
    public sealed class Mesh
    {
        Vector3[] _vertices = new Vector3[0], _normals = new Vector3[0];
        int[] _triangles = new int[0];

        public string name = "";
        public Vector2[] uv = new Vector2[0];
        public Bounds bounds { get; private set; }
        public int vertexCount => _vertices.Length;

        public Vector3[] vertices { get => (Vector3[])_vertices.Clone(); set => _vertices = (Vector3[])value.Clone(); }
        public Vector3[] normals { get => (Vector3[])_normals.Clone(); set => _normals = (Vector3[])value.Clone(); }

        // Unity rejects indices outside the vertex array; this shim throws.
        public int[] triangles
        {
            get => (int[])_triangles.Clone();
            set
            {
                if (value.Length % 3 != 0) throw new ArgumentException("triangle index count must be a multiple of 3");
                foreach (int i in value)
                    if (i < 0 || i >= _vertices.Length) throw new ArgumentException($"triangle index {i} out of bounds ({_vertices.Length} vertices)");
                _triangles = (int[])value.Clone();
            }
        }

        public void SetVertices(List<Vector3> v) => vertices = v.ToArray();
        public void SetNormals(List<Vector3> n) => normals = n.ToArray();
        public void SetTriangles(int[] t, int submesh) => triangles = t;
        public void SetTriangles(List<int> t, int submesh) => triangles = t.ToArray();
        public void Clear() { _vertices = new Vector3[0]; _normals = new Vector3[0]; _triangles = new int[0]; uv = new Vector2[0]; }

        // Each vertex gets the normalized sum of the face normals Cross(b - a, c - a) of its triangles.
        public void RecalculateNormals()
        {
            var sum = new Vector3[_vertices.Length];
            for (int t = 0; t < _triangles.Length; t += 3)
            {
                int i = _triangles[t], j = _triangles[t + 1], k = _triangles[t + 2];
                Vector3 n = Vector3.Cross(_vertices[j] - _vertices[i], _vertices[k] - _vertices[i]);
                sum[i] += n; sum[j] += n; sum[k] += n;
            }
            _normals = new Vector3[_vertices.Length];
            for (int v = 0; v < sum.Length; v++) _normals[v] = sum[v].normalized;
        }

        public void RecalculateBounds()
        {
            if (_vertices.Length == 0) { bounds = new Bounds(); return; }
            Vector3 lo = _vertices[0], hi = _vertices[0];
            foreach (Vector3 v in _vertices)
            {
                lo = new Vector3(Math.Min(lo.x, v.x), Math.Min(lo.y, v.y), Math.Min(lo.z, v.z));
                hi = new Vector3(Math.Max(hi.x, v.x), Math.Max(hi.y, v.y), Math.Max(hi.z, v.z));
            }
            bounds = new Bounds((lo + hi) * 0.5f, hi - lo);
        }
    }

    public class GameObject
    {
        public string name;
        public Transform transform { get; }
        public bool activeSelf { get; private set; } = true;
        public GameObject() : this("New Game Object") { }
        public GameObject(string name) { this.name = name; transform = new Transform(this); }
        public void SetActive(bool value) => activeSelf = value;
    }

    // Local TRS like Unity: a point is scaled, then rotated, then translated, then the same
    // happens for each parent up the chain.
    public sealed class Transform
    {
        readonly List<Transform> _children = new List<Transform>();
        Transform _parent;

        internal Transform(GameObject go) { gameObject = go; }

        public GameObject gameObject { get; }
        public string name { get => gameObject.name; set => gameObject.name = value; }
        public Vector3 localPosition = Vector3.zero;
        public Quaternion localRotation = Quaternion.identity;
        public Vector3 localScale = Vector3.one;

        public Transform parent { get => _parent; set => SetParent(value, true); }
        public int childCount => _children.Count;
        public Transform GetChild(int index) => _children[index];

        public void SetParent(Transform parent) => SetParent(parent, true);
        public void SetParent(Transform parent, bool worldPositionStays)
        {
            Vector3 pos = position, scale = lossyScale;
            Quaternion rot = rotation;
            _parent?._children.Remove(this);
            _parent = parent;
            parent?._children.Add(this);
            if (!worldPositionStays) return;
            Vector3 ps = parent == null ? Vector3.one : parent.lossyScale;
            localPosition = parent == null ? pos : parent.InverseTransformPoint(pos);
            localRotation = parent == null ? rot : Quaternion.Inverse(parent.rotation) * rot;
            localScale = new Vector3(scale.x / ps.x, scale.y / ps.y, scale.z / ps.z);
        }

        public Vector3 position
        {
            get => _parent == null ? localPosition : _parent.TransformPoint(localPosition);
            set => localPosition = _parent == null ? value : _parent.InverseTransformPoint(value);
        }

        public Quaternion rotation
        {
            get => _parent == null ? localRotation : _parent.rotation * localRotation;
            set => localRotation = _parent == null ? value : Quaternion.Inverse(_parent.rotation) * value;
        }

        public Vector3 lossyScale => _parent == null ? localScale : Vector3.Scale(_parent.lossyScale, localScale);

        public Vector3 TransformPoint(Vector3 p)
        {
            Vector3 local = localRotation * Vector3.Scale(localScale, p) + localPosition;
            return _parent == null ? local : _parent.TransformPoint(local);
        }

        public Vector3 InverseTransformPoint(Vector3 p)
        {
            Vector3 inParent = _parent == null ? p : _parent.InverseTransformPoint(p);
            Vector3 r = Quaternion.Inverse(localRotation) * (inParent - localPosition);
            return new Vector3(r.x / localScale.x, r.y / localScale.y, r.z / localScale.z);
        }

        public Vector3 TransformDirection(Vector3 d) => rotation * d;
        public Vector3 forward => rotation * Vector3.forward;
        public Vector3 up => rotation * Vector3.up;
        public Vector3 right => rotation * Vector3.right;

        // A direct child by name, or a path such as "hull/bow".
        public Transform Find(string path)
        {
            Transform t = this;
            foreach (string part in path.Split('/'))
            {
                Transform next = null;
                foreach (Transform c in t._children) if (c.name == part) { next = c; break; }
                if (next == null) return null;
                t = next;
            }
            return t;
        }
    }

    // Only the subset of Unity's KeyCode values that tasks use; the numbers are Unity's.
    public enum KeyCode
    {
        None = 0, Backspace = 8, Tab = 9, Return = 13, Escape = 27, Space = 32,
        Alpha0 = 48, Alpha1 = 49, Alpha2 = 50, Alpha3 = 51, Alpha4 = 52, Alpha5 = 53, Alpha6 = 54, Alpha7 = 55, Alpha8 = 56, Alpha9 = 57,
        A = 97, B = 98, C = 99, D = 100, E = 101, F = 102, G = 103, H = 104, I = 105, J = 106, K = 107, L = 108, M = 109,
        N = 110, O = 111, P = 112, Q = 113, R = 114, S = 115, T = 116, U = 117, V = 118, W = 119, X = 120, Y = 121, Z = 122,
        UpArrow = 273, DownArrow = 274, RightArrow = 275, LeftArrow = 276,
        RightShift = 303, LeftShift = 304, RightControl = 305, LeftControl = 306,
    }

    // The old Input Manager: GetKeyDown/GetKeyUp are true only during the frame the key went
    // down/up, GetKey while it is held. No key repeat.
    public static class Input
    {
        static readonly HashSet<KeyCode> Held = new HashSet<KeyCode>(), Down = new HashSet<KeyCode>(), Up = new HashSet<KeyCode>();

        public static bool GetKey(KeyCode key) => Held.Contains(key);
        public static bool GetKeyDown(KeyCode key) => Down.Contains(key);
        public static bool GetKeyUp(KeyCode key) => Up.Contains(key);
        public static bool anyKey => Held.Count > 0;
        public static bool anyKeyDown => Down.Count > 0;

        // Test helpers, not part of Unity's API: state changes made between two NextFrame calls are
        // what the code sees during that frame.
        public static void SimulatePress(KeyCode key) { if (Held.Add(key)) Down.Add(key); }
        public static void SimulateRelease(KeyCode key) { if (Held.Remove(key)) Up.Add(key); }
        public static void NextFrame() { Down.Clear(); Up.Clear(); }
        public static void Reset() { Held.Clear(); Down.Clear(); Up.Clear(); }
    }

    public class Component
    {
        public GameObject gameObject { get; internal set; }
        public Transform transform => gameObject?.transform;
    }

    // Plain base class here: Unity never calls Awake/Start/Update in this shim, tests do.
    public class MonoBehaviour : Component { }

    public static class Debug
    {
        static readonly object Gate = new object();
        static readonly List<string> Lines = new List<string>();

        public static void Log(object message) => Append("LOG", message);
        public static void LogWarning(object message) => Append("WARN", message);
        public static void LogError(object message) => Append("ERROR", message);
        public static void LogException(Exception exception) => Append("EXCEPTION", exception);

        // Test helper, not part of Unity's API.
        public static string[] Snapshot()
        {
            lock (Gate) return Lines.ToArray();
        }

        static void Append(string level, object message)
        {
            lock (Gate) Lines.Add($"{level}: {message}");
        }
    }
}
