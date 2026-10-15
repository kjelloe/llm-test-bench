// shared/const.mjs — every tuning value in the game. No logic here.

export const TICK_HZ = 20;
export const TICK_MS = 1000 / TICK_HZ;

export const CELL = 256; // fixed-point world units per cell
export const HALF = 128; // entities live at cell centres
export const GRID_W = 25; // border walls included; odd so pillars land
export const GRID_H = 17;

export const MAX_PLAYERS = 16;
export const BODY = 108; // player half-extent, < HALF so corners forgive
export const ASSIST_MIN = 64; // lane offset before a corner slide kicks in

export const SPEED_BASE = 56; // units/tick (~4.4 cells/s at 20 Hz)
export const SPEED_STEP = 10; // per speed power-up
export const SPEED_MAX = 96;

export const BOMB_FUSE_TICKS = 40; // 2 s
export const FLAME_TICKS = 10; // 0.5 s
export const BLAST_BASE = 2; // cells per ray
export const BLAST_MAX = 8;
export const BOMB_CAP_BASE = 1;
export const BOMB_CAP_MAX = 6;
export const REMOTE_FUSE_TICKS = 10 * TICK_HZ; // failsafe on remote bombs

export const SOFT_BLOCK_P = 0.52; // chance a free cell gets a soft block
export const DROP_P = 0.28; // chance a destroyed block reveals a power-up
export const INVULN_TICKS = 60; // 3 s spawn protection

export const COUNTDOWN_TICKS = 5 * TICK_HZ; // P13: 5 s round countdown
export const ROUND_TICKS = 120 * TICK_HZ;
export const SHRINK_TICKS = 30 * TICK_HZ; // shrink runs the last 30 s
export const RESULTS_TICKS = 8 * TICK_HZ;

// Lobby: first human starts the clock; late humans bump it back up a bit;
// bots fill the arena to BOT_FILL_TOTAL and yield seats to humans.
export const LOBBY_COUNTDOWN_TICKS = 15 * TICK_HZ; // P13: 15 s gather time
export const LOBBY_JOIN_BUMP_TICKS = 5 * TICK_HZ;
export const BOT_FILL_TOTAL = 8;
export const BOT_THINK_TICKS = 4; // a bot re-plans every 200 ms
export const BOT_NAMES = [
  'BOLTZ', 'FUZE', 'CINDER', 'SPARKY', 'WICK', 'NITRO', 'KABOOM', 'EMBER',
  'DYNAMO', 'BLASTA', 'SIZZLE', 'ROCKETTE', 'TNTINA', 'MATCHES', 'ASHES', 'POPKORN'
];

export const RECONNECT_GRACE_MS = 10000;
export const INTERP_DELAY_MS = 100;

export const T = { FLOOR: '.', WALL: '#', BLOCK: '+' };

export const PU = { BOMB: 'b', BLAST: 'r', SPEED: 's', REMOTE: 't' };

export const PLAYER_COLORS = [
  '#ff3df0', '#2bfcff', '#ffe93d', '#3dff6e',
  '#ff8a3d', '#8a6bff', '#ff4d5e', '#5effc3',
  '#ffb3f5', '#9bd7ff', '#fff3a1', '#b6ffb0',
  '#ffc98a', '#c9b8ff', '#ff9aa5', '#a1ffe8'
];
