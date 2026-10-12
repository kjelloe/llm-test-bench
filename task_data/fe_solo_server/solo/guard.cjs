// Preloaded into the single-player server (node -r): the client holds this process's stdin open, so when the
// client exits (or dies) stdin ends and the server goes with it, on Linux and Windows alike (PLAN D7). A server
// that listens for SIGTERM (CarrierDominion saves its war there) gets that first; signals sent to node on
// Windows never reach a handler, so the guard raises it in-process, then exits if the handler has not.
function stop() {
  if (!process.emit('SIGTERM')) process.exit(0);
  setTimeout(() => process.exit(0), 2000).unref();
}
process.stdin.on('end', stop);
process.stdin.on('error', stop);
process.stdin.resume();
