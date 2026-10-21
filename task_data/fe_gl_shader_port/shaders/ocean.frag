  uniform vec3 uShallow;
  uniform vec3 uDeep;
  uniform float uTime;
  varying vec3 vWorld;
  varying float vDetail;
  void main() {
    float ripple = 0.5 + 0.5 * sin(vWorld.x * 0.014 + vWorld.z * 0.011 + uTime * 1.7) * vDetail;
    vec3 colour = mix(uDeep, uShallow, ripple * 0.35);
    gl_FragColor = vec4(colour, 1.0);
  }
