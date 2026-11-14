//! A minimal stand-in for the parts of Bevy this task needs (read-only). Bevy itself compiles far too slowly per task;
//! this keeps its rules where they matter:
//!
//! - A frame runs three stages in order: PreUpdate, Update, PostUpdate. Inside a stage, systems run in an order that
//!   respects every `.after(name)` / `.before(name)` constraint; systems that are not ordered relative to each other
//!   run in an arbitrary order (this shim: by name). Like Bevy, registering order means nothing.
//! - `Assets<Material>`: `get_mut` marks the asset changed, whether or not anything is written (Bevy's change
//!   detection works the same way); every changed material is uploaded to the GPU again in PostUpdate.
//! - Engine systems, added by `App::new`: `sync_transforms` (Update) copies every entity's simulated position into its
//!   transform, each frame; `light_system` (PostUpdate) sets each sun's illuminance from its `LightBase` and the time
//!   of day, each frame; `upload_materials` (PostUpdate) uploads the changed materials; `extract` (PostUpdate, last)
//!   records what the renderer will draw.
use std::f64::consts::PI;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Stage {
    PreUpdate,
    Update,
    PostUpdate,
}

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Vec3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Handle(pub usize);

#[derive(Debug, Clone, PartialEq)]
pub struct Material {
    pub color: [f32; 3],
}

#[derive(Default)]
pub struct Assets {
    items: Vec<Material>,
    changed: Vec<bool>,
}

impl Assets {
    pub fn add(&mut self, m: Material) -> Handle {
        self.items.push(m);
        self.changed.push(true);
        Handle(self.items.len() - 1)
    }
    pub fn get(&self, h: Handle) -> &Material {
        &self.items[h.0]
    }
    /// Marks the material changed, even if the caller writes nothing.
    pub fn get_mut(&mut self, h: Handle) -> &mut Material {
        self.changed[h.0] = true;
        &mut self.items[h.0]
    }
}

/// A sun's lighting input, owned by the game: `light_system` derives the sun's illuminance from it each frame.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct LightBase {
    pub lux: f32,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Sun {
    pub illuminance: f32,
}

#[derive(Debug, Clone, Default)]
pub struct Entity {
    /// The simulation's position (from the server); `sync_transforms` copies it into `transform` each frame.
    pub sim: Option<Vec3>,
    pub transform: Option<Vec3>,
    pub team: Option<u8>,
    pub material: Option<Handle>,
    /// Visual wave heave amplitude, metres.
    pub heave: Option<f32>,
    pub sun: Option<Sun>,
    pub light_base: Option<LightBase>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Drawn {
    pub transforms: Vec<Option<Vec3>>,
    pub sun_illuminance: Vec<Option<f32>>,
    pub uploads: usize,
}

pub struct World {
    pub entities: Vec<Entity>,
    pub materials: Assets,
    /// Seconds since the start, set by `App::update`.
    pub time: f64,
    /// Cloud cover in [0, 1], from the server's weather.
    pub cloud: f32,
    pub drawn: Vec<Drawn>,
    uploads_this_frame: usize,
}

/// The time-of-day factor `light_system` applies (1 at noon, the start).
pub fn daylight(time: f64) -> f32 {
    (0.6 + 0.4 * (time * 2.0 * PI / 600.0).cos()) as f32
}

pub type System = fn(&mut World);

struct Entry {
    name: &'static str,
    stage: Stage,
    after: Vec<&'static str>,
    before: Vec<&'static str>,
    run: System,
}

pub struct App {
    pub world: World,
    systems: Vec<Entry>,
}

/// Returned by `add_system`, to state its order.
pub struct SystemConfig<'a> {
    entry: &'a mut Entry,
}

impl SystemConfig<'_> {
    pub fn after(self, name: &'static str) -> Self {
        self.entry.after.push(name);
        self
    }
    pub fn before(self, name: &'static str) -> Self {
        self.entry.before.push(name);
        self
    }
}

fn sync_transforms(w: &mut World) {
    for e in &mut w.entities {
        if let Some(p) = e.sim {
            e.transform = Some(p);
        }
    }
}

fn light_system(w: &mut World) {
    let d = daylight(w.time);
    for e in &mut w.entities {
        if let (Some(sun), Some(base)) = (e.sun.as_mut(), e.light_base) {
            sun.illuminance = base.lux * d;
        }
    }
}

fn upload_materials(w: &mut World) {
    w.uploads_this_frame = w.materials.changed.iter().filter(|c| **c).count();
    w.materials.changed.iter_mut().for_each(|c| *c = false);
}

fn extract(w: &mut World) {
    let d = Drawn {
        transforms: w.entities.iter().map(|e| e.transform).collect(),
        sun_illuminance: w.entities.iter().map(|e| e.sun.map(|s| s.illuminance)).collect(),
        uploads: w.uploads_this_frame,
    };
    w.drawn.push(d);
}

impl App {
    pub fn new() -> App {
        let world = World { entities: Vec::new(), materials: Assets::default(), time: 0.0, cloud: 0.0, drawn: Vec::new(), uploads_this_frame: 0 };
        let mut app = App { world, systems: Vec::new() };
        app.add_system("sync_transforms", Stage::Update, sync_transforms);
        app.add_system("light_system", Stage::PostUpdate, light_system);
        app.add_system("upload_materials", Stage::PostUpdate, upload_materials).after("light_system");
        app.add_system("extract", Stage::PostUpdate, extract).after("upload_materials");
        app
    }

    pub fn add_system(&mut self, name: &'static str, stage: Stage, run: System) -> SystemConfig<'_> {
        assert!(self.systems.iter().all(|s| s.name != name), "system {name} added twice");
        self.systems.push(Entry { name, stage, after: Vec::new(), before: Vec::new(), run });
        SystemConfig { entry: self.systems.last_mut().unwrap() }
    }

    /// The order the systems run in, by name.
    pub fn order(&self) -> Vec<&'static str> {
        let mut out = Vec::new();
        for stage in [Stage::PreUpdate, Stage::Update, Stage::PostUpdate] {
            let mut left: Vec<&Entry> = self.systems.iter().filter(|s| s.stage == stage).collect();
            left.sort_by_key(|s| s.name);
            let names: Vec<&str> = left.iter().map(|s| s.name).collect();
            let must_wait = |s: &Entry, left: &[&Entry]| {
                s.after.iter().any(|a| names.contains(a) && left.iter().any(|l| l.name == *a))
                    || left.iter().any(|l| l.before.contains(&s.name))
            };
            while !left.is_empty() {
                let i = (0..left.len()).find(|&i| !must_wait(left[i], &left)).expect("ordering cycle");
                out.push(left.remove(i).name);
            }
        }
        out
    }

    /// One frame at `time` seconds.
    pub fn update(&mut self, time: f64) {
        self.world.time = time;
        for name in self.order() {
            let run = self.systems.iter().find(|s| s.name == name).unwrap().run;
            run(&mut self.world);
        }
    }
}

impl Default for App {
    fn default() -> Self {
        App::new()
    }
}
