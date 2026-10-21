precision highp float;
varying vec2 vCell;
void main() { gl_FragColor = vec4(vCell.x / 200.0, vCell.y / 100.0, 0.5, 1.0); }
