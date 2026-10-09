// Prints tests/GameClientTests/fixtures.json from the real library (js/qrcode.mjs), exactly as the
// browser client calls it: qrcode(0, 'M'), addData(text), make().
// Run: node js/make-fixtures.mjs > tests/GameClientTests/fixtures.json
import { qrcode } from './qrcode.mjs';

// Byte capacity at level M for versions 1-10.
const CAPACITY = [14, 26, 42, 62, 84, 106, 122, 152, 180, 213];
const base = 'http://192.168.1.20:8080/?join=';

function url(len) {
  let s = base;
  let i = 0;
  while (s.length < len) s += 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789-'[i++ % 33];
  return s.slice(0, len);
}

function encode(text) {
  const qr = qrcode(0, 'M');
  qr.addData(text);
  qr.make();
  const n = qr.getModuleCount();
  const rows = [];
  for (let r = 0; r < n; r++) {
    let row = '';
    for (let c = 0; c < n; c++) row += qr.isDark(r, c) ? '1' : '0';
    rows.push(row);
  }
  return { text, version: (n - 17) / 4, modules: rows };
}

const texts = ['A', 'http://x/', 'http://10.0.0.2:8080/'];
// Each version's capacity and one byte more (which must move to the next version); 212/213 for version 10.
for (const cap of CAPACITY) {
  for (const len of cap === 213 ? [212, 213] : [cap, cap + 1]) texts.push(len <= base.length ? base.slice(0, len) : url(len));
}
// Characters outside ASCII: the library keeps only the low byte of each UTF-16 unit.
texts.push('wss://spill.example/?name=Bjørn&join=ÆØÅ-ñ&cost=5€&dir=→');
const cases = texts.map(encode);
const tooLong = [url(214), url(300)];
process.stdout.write(JSON.stringify({ cases, tooLong }) + '\n');
