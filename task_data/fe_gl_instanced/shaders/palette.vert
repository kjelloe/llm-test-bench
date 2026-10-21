precision highp float;
attribute vec3 aColor;
attribute vec2 aOffset;
varying vec3 vColor;
void main() {
  vColor = aColor;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position.xy * 12.0 + aOffset, 0.0, 1.0);
}
