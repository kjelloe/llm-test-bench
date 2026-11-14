// MeshLambertMaterial, ported from three r162 to WGSL for bj-engine's Lambert pass. It must give what three draws
// (NoToneMapping, sRGB output). Reference: shaders/three-r162-lambert.txt.
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

const PI: f32 = 3.141592653589793;

fn to_linear(c: vec3<f32>) -> vec3<f32> {
    return select(pow(c * 0.9478672986 + vec3(0.0521327014), vec3(2.4)), c * 0.0773993808, c < vec3(0.04045));
}

fn to_srgb(c: vec3<f32>) -> vec3<f32> {
    return select(1.055 * pow(c, vec3(1.0 / 2.4)) - vec3(0.055), c * 12.92, c <= vec3(0.0031308));
}

@fragment
fn fs() -> @location(0) vec4<f32> {
    let n = normalize(u.normal.xyz);
    var irradiance = to_linear(u.ambient.rgb) * u.ambient.w;
    let sky = to_linear(u.sky.rgb) * u.sky.w;
    let ground = to_linear(u.ground.rgb) * u.sky.w;
    irradiance += mix(ground, sky, n.y * 0.5 + 0.5);
    for (var i = 0; i < i32(u.counts.x); i++) {
        let s = u.suns[i];
        irradiance += to_linear(s.color.rgb) * s.color.w * max(dot(n, normalize(s.direction.xyz)), 0.0);
    }
    let diffuse = irradiance * to_linear(u.material.rgb) / PI;
    return vec4(to_srgb(clamp(diffuse, vec3(0.0), vec3(1.0))), 1.0);
}
