precision highp float;
attribute vec2 aCell;
varying vec2 vCell;
void main() {
  vCell = aCell;
  gl_Position = projectionMatrix * modelViewMatrix * vec4((position.xy + aCell + 0.5) * 2.0, 0.0, 1.0);
}
