
  precision highp float;
  attribute vec3 aSeed;
  uniform float uTime;
  uniform float uFall;
  uniform vec2 uWind;
  uniform float uSlant;
  uniform vec3 uBox;
  uniform float uShare;
  uniform float uLength;
  varying float vFade;

  void main() {
    // Each drop keeps its own column of air and falls down it forever,
    // wrapping at the bottom, and that mod() is the whole animation: nothing is
    // written back and nothing is updated on the CPU.
    float phase = mod(uTime * uFall + aSeed.y * 977.0, uBox.y);
    vec3 local = vec3((aSeed.x - 0.5) * uBox.x, uBox.y * 0.5 - phase, (aSeed.z - 0.5) * uBox.z);
    // The wind carries a drop sideways as it falls, so rain slants with the
    // same wind that raised the sea. A vertical downpour beside a running sea
    // is the tell that two systems are not talking to each other.
    local.xz += uWind * (phase * uSlant);

    // A drop the storm is not heavy enough to have gets parked far below and
    // faded out, rather than branching in the shader.
    float carried = step(aSeed.x, uShare);

    vec3 fallDir = normalize(vec3(uWind.x * uSlant, -1.0, uWind.y * uSlant));
    vec4 mv = modelViewMatrix * vec4(local, 1.0);
    // Billboard the streak: across the view, stretched along the fall.
    vec3 viewFall = normalize((modelViewMatrix * vec4(fallDir, 0.0)).xyz);
    vec3 across = normalize(cross(viewFall, vec3(0.0, 0.0, 1.0)));
    mv.xyz += across * position.x * 0.06;
    mv.xyz += viewFall * position.y * uLength;

    // Fade at the box's rim so drops arrive and leave rather than popping,
    // and fade the very near ones so the eye is not full of streaks.
    float far = 1.0 - smoothstep(uBox.x * 0.34, uBox.x * 0.56, length(mv.xyz));
    float near = smoothstep(1.2, 5.0, length(mv.xyz));
    vFade = far * near * carried;
    gl_Position = projectionMatrix * mv;
  }
