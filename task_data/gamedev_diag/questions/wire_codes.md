# wire_codes

The browser client turns local prediction on when the local player's state is alive. In the Unity port, a test that replays a captured real match reports 'predictor never active', though the player moves for 40 seconds. The port checks `(string)player["state"] == "alive"` on the parsed snapshot JSON. What is the most likely cause?

A. The capture missed the join message, so the client never learns which player in the snapshot is its own.
B. Coalesced snapshots skipped the one view in which the player's state changed to alive.
C. The wire carries a compact code (e.g. "a") that the browser decodes; the port compares it to the name.
D. Newtonsoft parses "alive" into an enum value, so the string comparison never matches.
E. The predictor also needs the tick rate from the hello message, which the captured replay does not contain.
