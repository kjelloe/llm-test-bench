// A stand-in for a game's Node server, unchanged by the client: it listens on PORT, announces itself on stdout,
// and saves its game to SAVE (taking 400 ms) when it gets SIGTERM. Test switches: CRASH=1 exits with code 3 after starting;
// STUBBORN=1 ignores SIGTERM and keeps running (busy), so only a kill stops it.
const http = require('http');
const fs = require('fs');
const port = Number(process.env.PORT);
const server = http.createServer((req, res) => { res.writeHead(200); res.end('ok'); });
server.listen(port, process.env.HOST || '127.0.0.1', () => {
  console.log(`serving on http://localhost:${port}`);
  console.log(`serving on http://localhost:${port}`);   // some servers announce twice
  console.error(`env MODE=${process.env.MODE} SAVE=${process.env.SAVE} STATE_DIR=${process.env.STATE_DIR}`);
  if (process.env.CRASH === '1') setTimeout(() => process.exit(3), 200);
});
process.on('SIGTERM', () => {
  if (process.env.STUBBORN === '1') { for (;;) { /* never yields: the guard's own exit timer cannot run */ } }
  setTimeout(() => {   // a real autosave takes a moment
    fs.writeFileSync(process.env.SAVE, JSON.stringify({ saved: true, pid: process.pid }));
    console.log('saved');
    process.exit(0);
  }, 400);
});
