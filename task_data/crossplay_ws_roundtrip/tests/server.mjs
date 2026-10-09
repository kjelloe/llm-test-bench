// A minimal authoritative match server for the round-trip test: Node stdlib only, its own RFC 6455
// framing. Seats with reclaim tokens (as CarrierDominion's server does), numbered commands with acks.
// Prints "port N" when listening. Test control on stdin, one per line:
//   drop T       destroy team T's socket without a close frame (a network drop)
//   supersede T  close team T's socket with code 4000 (another device took the seat)
//   log T        print "log T <json>": every command seq received from team T, in arrival order
//   welcomes T   print "welcomes T <json>": [{reclaimed}] for each welcome sent to team T
import { createServer } from 'node:http';
import { createHash, randomBytes } from 'node:crypto';
import { createInterface } from 'node:readline';

const GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
const seats = new Map(); // team -> { token, socket, received: [], welcomes: [] }

function frame(opcode, payload) {
  const len = payload.length;
  const head = len < 126 ? Buffer.from([0x80 | opcode, len])
    : len < 65536 ? Buffer.from([0x80 | opcode, 126, len >> 8, len & 255])
      : Buffer.concat([Buffer.from([0x80 | opcode, 127]), (() => { const b = Buffer.alloc(8); b.writeBigUInt64BE(BigInt(len)); return b; })()]);
  return Buffer.concat([head, payload]);
}

const sendText = (socket, obj) => socket.write(frame(1, Buffer.from(JSON.stringify(obj))));

function closeWith(socket, code, reason) {
  const p = Buffer.alloc(2 + Buffer.byteLength(reason));
  p.writeUInt16BE(code, 0);
  p.write(reason, 2);
  socket.end(frame(8, p));
}

function onMessage(seat, socket, text) {
  if (seat.socket !== socket) return; // a superseded socket no longer speaks for the seat
  const msg = JSON.parse(text);
  if (msg.type === 'command') {
    seat.received.push(msg.seq);
    sendText(socket, { type: 'ack', seq: msg.seq });
  }
}

function attach(socket, url) {
  const token = url.searchParams.get('token') ?? '';
  let team = -1;
  for (const [t, s] of seats) if (token !== '' && s.token === token) team = t;
  const reclaimed = team !== -1;
  if (!reclaimed) {
    team = seats.size;
    seats.set(team, { token: randomBytes(9).toString('base64url'), socket: null, received: [], welcomes: [] });
  }
  const seat = seats.get(team);
  if (seat.socket && seat.socket !== socket) closeWith(seat.socket, 4000, 'superseded');
  seat.socket = socket;
  seat.welcomes.push({ reclaimed });
  sendText(socket, { type: 'welcome', team, token: seat.token, reclaimed });

  let buf = Buffer.alloc(0);
  let parts = [];
  socket.on('data', (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    for (;;) {
      if (buf.length < 2) return;
      const fin = (buf[0] & 0x80) !== 0, op = buf[0] & 15, masked = (buf[1] & 0x80) !== 0;
      let len = buf[1] & 127, off = 2;
      if (len === 126) { if (buf.length < 4) return; len = buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { if (buf.length < 10) return; len = Number(buf.readBigUInt64BE(2)); off = 10; }
      if (!masked) { socket.destroy(); return; } // clients must mask (RFC 6455 5.1)
      if (buf.length < off + 4 + len) return;
      const mask = buf.subarray(off, off + 4);
      const data = Buffer.from(buf.subarray(off + 4, off + 4 + len));
      for (let i = 0; i < data.length; i++) data[i] ^= mask[i % 4];
      buf = buf.subarray(off + 4 + len);
      if (op === 8) { socket.end(frame(8, data)); return; }
      if (op === 9) { socket.write(frame(10, data)); continue; }
      if (op === 10) continue;
      parts.push(data);
      if (fin) { onMessage(seat, socket, Buffer.concat(parts).toString()); parts = []; }
    }
  });
  socket.on('error', () => {});
  socket.on('close', () => { if (seat.socket === socket) seat.socket = null; });
}

const server = createServer((req, res) => { res.writeHead(426); res.end(); });
server.on('upgrade', (req, socket) => {
  const key = req.headers['sec-websocket-key'];
  if (!key || req.headers['sec-websocket-version'] !== '13') { socket.destroy(); return; }
  const accept = createHash('sha1').update(key + GUID).digest('base64');
  socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
  socket.setNoDelay(true);
  attach(socket, new URL(req.url, 'http://localhost'));
});

server.listen(0, '127.0.0.1', () => console.log(`port ${server.address().port}`));
createInterface({ input: process.stdin }).on('line', (line) => {
  const [cmd, arg] = line.trim().split(/\s+/);
  const seat = seats.get(Number(arg));
  if (cmd === 'drop' && seat?.socket) seat.socket.destroy();
  else if (cmd === 'supersede' && seat?.socket) closeWith(seat.socket, 4000, 'superseded');
  else if (cmd === 'log') console.log(`log ${arg} ${JSON.stringify(seat ? seat.received : [])}`);
  else if (cmd === 'welcomes') console.log(`welcomes ${arg} ${JSON.stringify(seat ? seat.welcomes : [])}`);
});
process.stdin.on('end', () => process.exit(0));
