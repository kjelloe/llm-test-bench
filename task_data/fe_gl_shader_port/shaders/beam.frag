  precision highp float;
  uniform vec2 uSun;
  uniform float uStrength;
  uniform vec3 uColour;
  uniform float uAspect;
  uniform float uTime;
  varying vec2 vUv;

  float hash(float n) { return fract(sin(n) * 43758.5453); }

  void main() {
    if (uStrength <= 0.003) discard;
    vec2 d = vUv - uSun;
    d.x *= uAspect;
    float dist = length(d);
    float angle = atan(d.y, d.x);

    // The shafts themselves: a few dozen soft wedges around the sun, at fixed
    // angles that drift very slowly, so the light looks like it is coming
    // through moving cloud rather than through a fan.
    // FEW and BROAD. The first version used high frequencies and a hard
    // power, and the result was a lens flare - a sharp star pinned to the
    // sun. Crepuscular rays are wide soft wedges with gaps between them,
    // because they are the shape of the holes in the cloud, not the shape of
    // the sun.
    float rays = 0.0;
    for (int i = 0; i < 3; i++) {
      float f = 3.0 + float(i) * 4.0;
      float phase = hash(float(i) * 3.7) * 6.2831 + uTime * (0.010 + float(i) * 0.006);
      rays += (0.5 + 0.5 * sin(angle * f + phase)) * (0.5 - float(i) * 0.12);
    }
    rays = pow(clamp(rays, 0.0, 1.0), 1.5);

    // Bright at the sun, gone by the edge of the frame; and nothing at all
    // behind the eye, which is what a negative uSun.y would mean.
    // The shafts reach well down the frame; the glow around the sun itself is
    // kept small, because a big one is the flare look again.
    float falloff = exp(-dist * 2.0);
    float core = exp(-dist * 16.0);
    float a = (rays * falloff * 0.9 + core * 0.16) * uStrength;
    if (a <= 0.002) discard;
    gl_FragColor = vec4(uColour * a, a);
  }
