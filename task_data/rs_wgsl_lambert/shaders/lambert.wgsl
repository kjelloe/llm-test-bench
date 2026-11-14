// MeshLambertMaterial for bj-engine's Lambert pass, ported to WGSL from an old three.js lighting setup. It must give
// what three r162 draws for the same material and lights (NoToneMapping, sRGB output): physically correct light
// units, colours in linear space. shaders/three-r162-lambert.txt has the relevant parts of three r162.
// Keep this layout and the entry points: src/lib.rs fills the uniform buffer field by field (every field a vec4<f32>)
// and draws a full-target triangle with `vs`, then reads back the bytes `fs` returns (an Rgba8Unorm target: no
// automatic sRGB conversion).
struct Sun {
    color: vec4<f32>,      // rgb: sRGB 0..1, w: intensity
    direction: vec4<f32>,  // xyz: the light position minus its target (not normalised)
}

struct Lambert {
    material: vec4<f32>,   // rgb: the material colour, sRGB 0..1
    normal: vec4<f32>,     // xyz: the surface normal (not necessarily unit length)
    ambient: vec4<f32>,    // rgb: AmbientLight colour, sRGB; w: intensity
    sky: vec4<f32>,        // rgb: HemisphereLight sky colour, sRGB; w: its intensity (0 = no hemisphere light)
    ground: vec4<f32>,     // rgb: HemisphereLight ground colour, sRGB
    counts: vec4<f32>,     // x: how many of `suns` are used
    suns: array<Sun, 4>,
}

@group(0) @binding(0) var<uniform> u: Lambert;

@vertex
fn vs(@builtin(vertex_index) i: u32) -> @builtin(position) vec4<f32> {
    let p = array(vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
    return vec4(p[i], 0.0, 1.0);
}

fn to_srgb(c: vec3<f32>) -> vec3<f32> {
    return pow(c, vec3(1.0 / 2.2));
}

@fragment
fn fs() -> @location(0) vec4<f32> {
    let n = u.normal.xyz;
    var irradiance = u.ambient.rgb * u.ambient.w;
    for (var i = 0; i < i32(u.counts.x); i++) {
        let s = u.suns[i];
        irradiance += s.color.rgb * s.color.w * dot(n, -s.direction.xyz);
    }
    let diffuse = irradiance * u.material.rgb;
    return vec4(to_srgb(diffuse), 1.0);
}
