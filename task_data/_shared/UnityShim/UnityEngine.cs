// Minimal stand-in for the UnityEngine API, so Unity-style client code can be
// compiled and unit-tested with plain `dotnet test` (no Unity Editor).
// ONLY the members below exist. Anything else from UnityEngine (MonoBehaviour,
// Time, Transform, JsonUtility, eulerAngles, ...) is NOT available.
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
