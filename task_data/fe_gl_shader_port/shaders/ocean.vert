  uniform float uTime;
  varying vec3 vWorld;
  varying float vDetail;
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vDetail = 1.0 - smoothstep(900.0, 3600.0, length(cameraPosition - world.xyz));
    float w = sin(world.x * 0.012 + uTime * 1.1) * 0.9
            + sin(world.z * 0.017 - uTime * 0.8) * 0.7
            + sin((world.x + world.z) * 0.006 + uTime * 0.5) * 1.2;
    world.y += w * vDetail;
    vWorld = world.xyz;
    gl_Position = projectionMatrix * viewMatrix * world;
  }
