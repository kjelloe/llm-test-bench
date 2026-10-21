  uniform vec3 uShallow;
  uniform vec3 uDeep;
  uniform vec3 uSky;
  uniform vec3 uSunDir;
  uniform float uTime;
  varying vec3 vWorld;
  varying float vDetail;

  // Slope of the ripple field at this point: d/dx and d/dz of a handful of
  // travelling sines. Frequencies are spread irrationally so the pattern
  // never visibly repeats inside a map.
  vec2 rippleSlope(vec2 p, float t) {
    vec2 slope = vec2(0.0);
    slope += vec2(0.051, 0.033) * cos(dot(p, vec2(0.051, 0.033)) + t * 1.9) * 0.9;
    slope += vec2(-0.037, 0.061) * cos(dot(p, vec2(-0.037, 0.061)) - t * 1.4) * 0.7;
    slope += vec2(0.089, -0.074) * cos(dot(p, vec2(0.089, -0.074)) + t * 2.6) * 0.45;
    slope += vec2(0.153, 0.121) * cos(dot(p, vec2(0.153, 0.121)) - t * 3.4) * 0.25;
    slope += vec2(-0.201, 0.088) * cos(dot(p, vec2(-0.201, 0.088)) + t * 4.1) * 0.18;
    return slope;
  }

  void main() {
    vec2 slope = rippleSlope(vWorld.xz, uTime) * vDetail;
    vec3 normal = normalize(vec3(-slope.x, 1.0, -slope.y));
    vec3 view = normalize(cameraPosition - vWorld);

    float facing = max(dot(normal, view), 0.0);
    float fresnel = pow(1.0 - facing, 5.0);
    fresnel = 0.04 + 0.96 * fresnel;

    float ripple = 0.5 + 0.5 * sin(vWorld.x * 0.014 + vWorld.z * 0.011 + uTime * 1.7) * vDetail;
    vec3 body = mix(uDeep, uShallow, ripple * 0.35);
    vec3 colour = mix(body, uSky, fresnel * 0.6);

    // The glint path: tight and additive, brightest where the ripples happen
    // to mirror the sun into the eye - which is what sells the normals.
    float glint = pow(max(dot(reflect(-uSunDir, normal), view), 0.0), 160.0);
    colour += vec3(1.0, 0.93, 0.78) * glint * 0.9 * vDetail;

    gl_FragColor = vec4(colour, 1.0);
  }
