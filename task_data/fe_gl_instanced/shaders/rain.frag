
  precision highp float;
  uniform vec3 uColour;
  uniform float uStrength;
  varying float vFade;
  void main() {
    float a = vFade * uStrength;
    if (a <= 0.002) discard;
    gl_FragColor = vec4(uColour, a);
  }
