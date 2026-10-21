  precision highp float;
  varying vec2 vUv;
  void main() {
    vUv = uv;
    // A full-screen triangle in clip space; no camera involved.
    gl_Position = vec4(position.xy * 2.0, 0.0, 1.0);
  }
