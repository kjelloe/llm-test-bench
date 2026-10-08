// Regenerates tests/GameClientTests/fixtures.json from the JS specification.
// usage: node js/make-fixtures.js > tests/GameClientTests/fixtures.json
import { floorDiv, truncDiv, sampleCellX, fnv1a64, stateBytes, hashState } from './statehash.js';

const hex = bytes => Buffer.from(bytes).toString('hex');
const units = s => Array.from({ length: s.length }, (_, i) => s.charCodeAt(i)); // UTF-16 code units

const I32_MIN = -2147483648;
const I32_MAX = 2147483647;

const divCases = [
  [7, 2], [-7, 2], [7, -2], [-7, -2], [-1, 256], [-256, 256], [-257, 256], [255, 256],
  [0, 5], [I32_MIN, 256], [I32_MAX, 256], [I32_MIN, -1], [I32_MIN, 1], [-5, 1000],
];

const cellCases = [
  [0, 128], [255, 128], [256, 128], [16384, 128], [16385, 128], [16640, 128],
  [32512, 128], [-1, 128], [-256, 128], [-257, 128], [2560, 20], [2816, 20],
];

const fnvCases = ['', 'a', 'foobar', 'été'].map(s => {
  const bytes = Buffer.from(s, 'utf8');
  return { bytesHex: hex(bytes), hash: fnv1a64(bytes) };
});
fnvCases.push({ bytesHex: hex(Uint8Array.from({ length: 256 }, (_, i) => i)), hash: fnv1a64(Uint8Array.from({ length: 256 }, (_, i) => i)) });

const states = [
  { tick: 0, units: [] },
  {
    tick: 1042,
    units: [
      { id: 7, team: 1, x: -2048, y: 33024, heading: 192, hp: 100, alive: true, target: null, name: 'Bravo' },
      { id: 2, team: 0, x: 1408, y: 896, heading: 0, hp: 0, alive: false, target: 7, name: 'Alpha' },
      { id: 4000000000, team: 255, x: I32_MIN, y: I32_MAX, heading: 255, hp: 65535, alive: true, target: 0, name: '' },
    ],
  },
  {
    tick: 4294967295,
    units: [
      { id: 3, team: 2, x: 0, y: 0, heading: 64, hp: 50, alive: true, target: 4294967295, name: 'Søren Ærø' },
      { id: 1, team: 2, x: 1, y: -1, heading: 1, hp: 1, alive: true, target: null, name: '小龙 🚀' },
      { id: 9, team: 3, x: 5, y: 6, heading: 2, hp: 3, alive: false, target: null, name: 'broken\ud800pair' },
    ],
  },
];

const fixtures = {
  div: divCases.map(([a, b]) => ({ a, b, floor: floorDiv(a, b), trunc: truncDiv(a, b) })),
  sampleCellX: cellCases.map(([world, mapWidth]) => ({ world, mapWidth, cell: sampleCellX(world, mapWidth) })),
  fnv: fnvCases,
  states: states.map(s => ({
    tick: s.tick,
    units: s.units.map(u => ({ ...u, name: undefined, nameUnits: units(u.name) })),
    bytesHex: hex(stateBytes(s)),
    hash: hashState(s),
  })),
};

process.stdout.write(JSON.stringify(fixtures, null, 2) + '\n');
