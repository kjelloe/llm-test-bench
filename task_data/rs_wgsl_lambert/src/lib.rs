//! Renders lighting cases with shaders/lambert.wgsl on wgpu (Vulkan; Mesa's lavapipe where there is no GPU) and reads
//! each one's pixel back (read-only for this task). Each case is drawn into its own 4x4 Rgba8Unorm target: no automatic
//! sRGB conversion, so the bytes are exactly what the fragment shader returns.
use std::future::Future;
use std::sync::Arc;
use std::task::{Context, Poll, Wake, Waker};

pub const SHADER: &str = include_str!("../shaders/lambert.wgsl");

/// One directional light: colour as sRGB 0..1, intensity, and its position and target (it shines from position
/// towards target).
#[derive(Clone, Copy, Debug)]
pub struct Sun {
    pub color: [f32; 3],
    pub intensity: f32,
    pub position: [f32; 3],
    pub target: [f32; 3],
}

/// A flat surface and its lights, as three.js would set them up. Colours are sRGB 0..1 (three's `Color.setHex`).
#[derive(Clone, Debug)]
pub struct Case {
    pub material: [f32; 3],
    pub normal: [f32; 3],
    pub ambient: ([f32; 3], f32),
    /// sky colour, ground colour, intensity
    pub hemisphere: Option<([f32; 3], [f32; 3], f32)>,
    pub suns: Vec<Sun>,
}

fn uniform_bytes(c: &Case) -> Vec<u8> {
    // The layout of `struct Lambert` in the shader: every field a vec4<f32>.
    let mut f: Vec<f32> = Vec::new();
    let v4 = |f: &mut Vec<f32>, a: [f32; 3], w: f32| f.extend_from_slice(&[a[0], a[1], a[2], w]);
    v4(&mut f, c.material, 1.0);
    v4(&mut f, c.normal, 0.0);
    v4(&mut f, c.ambient.0, c.ambient.1);
    let (sky, ground, hi) = c.hemisphere.unwrap_or(([0.0; 3], [0.0; 3], 0.0));
    v4(&mut f, sky, hi);
    v4(&mut f, ground, 0.0);
    assert!(c.suns.len() <= 4, "at most four suns");
    v4(&mut f, [c.suns.len() as f32, 0.0, 0.0], 0.0);
    for i in 0..4 {
        match c.suns.get(i) {
            Some(s) => {
                v4(&mut f, s.color, s.intensity);
                let d = [s.position[0] - s.target[0], s.position[1] - s.target[1], s.position[2] - s.target[2]];
                v4(&mut f, d, 0.0);
            }
            None => {
                v4(&mut f, [0.0; 3], 0.0);
                v4(&mut f, [0.0; 3], 0.0);
            }
        }
    }
    f.iter().flat_map(|x| x.to_le_bytes()).collect()
}

struct Unpark(std::thread::Thread);
impl Wake for Unpark {
    fn wake(self: Arc<Self>) {
        self.0.unpark()
    }
}
fn block_on<F: Future>(f: F) -> F::Output {
    let mut f = Box::pin(f);
    let waker = Waker::from(Arc::new(Unpark(std::thread::current())));
    let mut cx = Context::from_waker(&waker);
    loop {
        if let Poll::Ready(v) = f.as_mut().poll(&mut cx) {
            return v;
        }
        std::thread::park();
    }
}

/// The pixel each case renders to, as [r, g, b, a] bytes. Panics with the compiler's message if the shader does not
/// compile.
pub fn render(cases: &[Case]) -> Vec<[u8; 4]> {
    let mut desc = wgpu::InstanceDescriptor::new_without_display_handle();
    desc.backends = wgpu::Backends::VULKAN;
    let instance = wgpu::Instance::new(desc);
    let adapter = block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).expect("no Vulkan adapter (install mesa-vulkan-drivers)");
    let (device, queue) = block_on(adapter.request_device(&wgpu::DeviceDescriptor::default())).expect("device");
    let scope = device.push_error_scope(wgpu::ErrorFilter::Validation);
    let module = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: Some("lambert.wgsl"), source: wgpu::ShaderSource::Wgsl(SHADER.into()) });
    let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
        label: None,
        entries: &[wgpu::BindGroupLayoutEntry {
            binding: 0,
            visibility: wgpu::ShaderStages::FRAGMENT,
            ty: wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Uniform, has_dynamic_offset: false, min_binding_size: None },
            count: None,
        }],
    });
    let pl = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor { label: None, bind_group_layouts: &[Some(&layout)], immediate_size: 0 });
    let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
        label: None,
        layout: Some(&pl),
        vertex: wgpu::VertexState { module: &module, entry_point: Some("vs"), buffers: &[], compilation_options: Default::default() },
        fragment: Some(wgpu::FragmentState { module: &module, entry_point: Some("fs"), targets: &[Some(wgpu::TextureFormat::Rgba8Unorm.into())], compilation_options: Default::default() }),
        primitive: Default::default(),
        depth_stencil: None,
        multisample: Default::default(),
        multiview_mask: None,
        cache: None,
    });
    if let Some(e) = block_on(scope.pop()) {
        panic!("the shader does not compile or does not match the harness: {e}");
    }
    let size = wgpu::Extent3d { width: 4, height: 4, depth_or_array_layers: 1 };
    let mut out = Vec::new();
    for c in cases {
        let bytes = uniform_bytes(c);
        let ubuf = device.create_buffer(&wgpu::BufferDescriptor { label: None, size: bytes.len() as u64, usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST, mapped_at_creation: false });
        queue.write_buffer(&ubuf, 0, &bytes);
        let bind = device.create_bind_group(&wgpu::BindGroupDescriptor { label: None, layout: &layout, entries: &[wgpu::BindGroupEntry { binding: 0, resource: ubuf.as_entire_binding() }] });
        let tex = device.create_texture(&wgpu::TextureDescriptor {
            label: None, size, mip_level_count: 1, sample_count: 1, dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8Unorm, usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC, view_formats: &[],
        });
        let view = tex.create_view(&Default::default());
        let read = device.create_buffer(&wgpu::BufferDescriptor { label: None, size: 256 * 4, usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ, mapped_at_creation: false });
        let mut enc = device.create_command_encoder(&Default::default());
        {
            let mut pass = enc.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: None,
                color_attachments: &[Some(wgpu::RenderPassColorAttachment { view: &view, depth_slice: None, resolve_target: None, ops: wgpu::Operations { load: wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT), store: wgpu::StoreOp::Store } })],
                ..Default::default()
            });
            pass.set_pipeline(&pipeline);
            pass.set_bind_group(0, &bind, &[]);
            pass.draw(0..3, 0..1);
        }
        enc.copy_texture_to_buffer(tex.as_image_copy(), wgpu::TexelCopyBufferInfo { buffer: &read, layout: wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(256), rows_per_image: None } }, size);
        queue.submit([enc.finish()]);
        read.slice(..).map_async(wgpu::MapMode::Read, |_| {});
        device.poll(wgpu::PollType::wait_indefinitely()).unwrap();
        let data = read.slice(..).get_mapped_range().unwrap();
        let p = 256 + 4; // row 1, column 1
        out.push([data[p], data[p + 1], data[p + 2], data[p + 3]]);
    }
    out
}
