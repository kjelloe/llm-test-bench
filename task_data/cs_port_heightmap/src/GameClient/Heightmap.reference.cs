namespace GameClient
{
    // Verbatim port of engine/heightmap.js islandHeightAt with shared/noise.js,
    // shared/fixed.js and prng.js mul32: integer only, same floor divisions, so
    // the mesh shows the coastline the server collides with. JS numbers are
    // exact below 2^53 here, which long covers. No UnityEngine, so Tests~ can
    // compare it against heights sampled from the JS.
    public static class Heightmap
    {
        public const long SeabedUnits = -51200;
        const long FalloffOne = 4096;
        const long SkirtPercent = 160;
        const long NoiseOne = 65536;
        const long SmoothOne = 1024;

        public static long SkirtRadius(Island island) => MulDiv(island.radius, SkirtPercent, 100);

        public static long IslandHeightAt(Island island, long wx, long wy)
        {
            var dx = wx - island.x;
            var dy = wy - island.y;
            long r = island.radius;
            var d2 = dx * dx + dy * dy;
            var skirt = SkirtRadius(island);
            var warpReach = MulDiv(r, island.warpPermil, 1000);
            var outerBound = skirt + warpReach;
            if (d2 >= outerBound * outerBound) return SeabedUnits;

            var warpNoise = ValueNoise2((long)island.seed + 991, wx, wy, island.warpCell) - 32768;
            var d = Isqrt(d2) + MulDiv(warpNoise, warpReach, 32768);
            if (d >= skirt) return SeabedUnits;
            if (d >= r)
            {
                var s = MulDiv(d - r, FalloffOne, skirt - r);
                return -MulDiv(-SeabedUnits, FloorDiv(s * s, FalloffOne), FalloffOne);
            }
            var clamped = d < 0 ? 0 : d;
            var t = FalloffOne - MulDiv(clamped, FalloffOne, r);
            var falloff = FloorDiv(t * t, FalloffOne);
            var baseHeight = MulDiv(island.peak, falloff, FalloffOne);
            var noise = Fbm2(island.seed, wx, wy, island.noiseCell, island.noiseOctaves) - 32768;
            var amplitude = MulDiv(island.peak, island.noisePermil, 1000);
            var relief = MulDiv(MulDiv(noise, amplitude, 32768), falloff, FalloffOne);
            return baseHeight + relief;
        }

        static long Fold16(long v) => ((v + 32768) % 65536 + 65536) % 65536;

        static long Mul32(long a, long b)
        {
            var aHi = a / 65536 % 65536;
            var aLo = a % 65536;
            return ((aHi * b % 65536) * 65536 + aLo * b) % 4294967296;
        }

        static long HashLattice(long seed, long gx, long gy)
        {
            var ux = Fold16(gx);
            var uy = Fold16(gy);
            var sum = (seed + Mul32(ux, 374761393) + Mul32(uy, 668265263)) % 4294967296;
            // JS `^` and `>>>` see the low 32 bits, also for a negative sum.
            var h = unchecked((uint)sum);
            h ^= h >> 13;
            h = (uint)Mul32(h, 1274126177);
            h ^= h >> 16;
            return h % NoiseOne;
        }

        static long Smoothstep(long f) => FloorDiv(f * f * (3 * SmoothOne - 2 * f), SmoothOne * SmoothOne);

        static long LerpI(long a, long b, long t) => a + FloorDiv((b - a) * t, SmoothOne);

        static long ValueNoise2(long seed, long x, long y, long cellSize)
        {
            var gx = FloorDiv(x, cellSize);
            var gy = FloorDiv(y, cellSize);
            var fx = Smoothstep(MulDiv(x - gx * cellSize, SmoothOne, cellSize));
            var fy = Smoothstep(MulDiv(y - gy * cellSize, SmoothOne, cellSize));
            var top = LerpI(HashLattice(seed, gx, gy), HashLattice(seed, gx + 1, gy), fx);
            var bottom = LerpI(HashLattice(seed, gx, gy + 1), HashLattice(seed, gx + 1, gy + 1), fx);
            return LerpI(top, bottom, fy);
        }

        static long Fbm2(long seed, long x, long y, long cellSize, long octaves)
        {
            long total = 0, normalisation = 0, amplitude = NoiseOne, cell = cellSize;
            for (var i = 0; i < octaves; i++)
            {
                var sample = ValueNoise2(seed + i * 7919, x, y, cell);
                total += FloorDiv(sample * amplitude, NoiseOne);
                normalisation += amplitude;
                amplitude = FloorDiv(amplitude, 2);
                cell = FloorDiv(cell, 2);
                if (cell < 1 || amplitude < 1) break;
            }
            if (normalisation < 1) return 0;
            return MulDiv(total, NoiseOne - 1, normalisation);
        }

        static long FloorDiv(long a, long b)
        {
            var q = a / b;
            return (a % b != 0 && (a < 0) != (b < 0)) ? q - 1 : q;
        }

        static long MulDiv(long a, long b, long c) => FloorDiv(a * b, c);

        static long Isqrt(long n)
        {
            if (n < 2) return n;
            long guess = 1;
            while (guess * guess <= n) guess *= 2;
            for (var i = 0; i < 40; i++)
            {
                var next = FloorDiv(guess + FloorDiv(n, guess), 2);
                if (next >= guess) break;
                guess = next;
            }
            while (guess * guess > n) guess--;
            while ((guess + 1) * (guess + 1) <= n) guess++;
            return guess;
        }
    }
}
