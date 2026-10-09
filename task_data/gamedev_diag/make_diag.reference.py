"""Generates task_data/gamedev_diag (questions, stub answers, hashed key). Contains the answers, so the
.reference name keeps it out of --export-task. Usage: python3 make_diag.reference.py task_data/gamedev_diag"""
import hashlib, json, sys
from pathlib import Path

ROOT = Path(sys.argv[1])
LETTERS = "ABCDE"
# (id, builder ref, question, correct option, [distractors], position of the correct option 0-4)
Q = [
("ws_abort", "C05",
 "A Unity client's receive loop is:\n\n```csharp\ntry { var r = await ws.ReceiveAsync(buffer, shutdown); /* ... */ }\ncatch (OperationCanceledException) { return; } // shutting down\ncatch (WebSocketException e) { OnClosed(e.Message); Reconnect(); }\n```\n\nTo simulate a network drop a tester calls `ws.Abort()` on the `ClientWebSocket` while a receive is pending. The connection goes silent and no reconnect ever happens. Why, and what is the fix?",
 "The aborted receive throws OperationCanceledException, which this loop takes for shutdown; only treat it as shutdown when the `shutdown` token is cancelled.",
 ["Abort() leaves the pending ReceiveAsync waiting for the server's FIN; call CloseAsync instead, which completes the pending receive at once and runs the reconnect path.",
  "The WebSocketException is raised on a thread-pool thread that Unity swallows; marshal it to the main thread before calling Reconnect.",
  "Abort() makes ReceiveAsync return a Close message with Count 0 that the elided code ignores; check MessageType for Close first.",
  "Abort() also cancels the `shutdown` token passed to ReceiveAsync; pass a fresh CancellationToken.None to every receive and keep the shutdown token for the loop only."], 1),
("emission_keyword", "D04",
 "An editor script generates URP Lit materials for team-coloured parts. It sets `_EmissionColor` to black and enables the `_EMISSION` keyword, planning to set the real emission colour per team at runtime. At runtime no emission shows, and the saved material no longer has the `_EMISSION` keyword. Why, and what is the fix?",
 "URP's material validation turns `_EMISSION` off when the emission colour is black; save the material with a non-black (e.g. white) emission.",
 ["URP strips shader keywords at build time unless the shader is listed in Always Included Shaders; add URP Lit to that list in Project Settings > Graphics before building.",
  "Keywords set on `sharedMaterial` are never written to the asset; set the keyword through `renderer.material` in the script.",
  "`_EMISSION` only takes effect when the material's global illumination flag is Baked; set globalIlluminationFlags to Baked.",
  "The SRP Batcher ignores emission set on the material itself; set `_EmissionColor` per renderer through a MaterialPropertyBlock instead of the material."], 3),
("emission_hdr", "D05",
 "A material's emission looks far too bright in the Unity port (Linear colour space), although its value comes from the same hex colour as the browser game: `mat.SetColor(\"_EmissionColor\", HexToColor(0x931c1c))`. Why, and what is the fix?",
 "`_EmissionColor` is an HDR property that Unity uses as linear; convert the sRGB hex value first with `HexToColor(...).linear`.",
 ["URP's default Volume adds bloom to every emissive surface; remove the Bloom override from the global Volume profile, or lower its intensity to zero.",
  "URP multiplies emission by the main light's intensity, which is above 1 here; divide the colour by the light's intensity.",
  "SetColor on an emission property expects 0-255 channel values, not 0-1; build the Color from the hex bytes with a Color32, which converts the range for you.",
  "The material is double-sided, so URP adds its emission once per face; switch Render Face back to Front only."], 0),
("gamma_project", "E01",
 "Colours from a three.js r162 game (colour management on) look washed out or too dark in its Unity port. The Unity project's Color Space is set to Gamma. What is the right fix?",
 "Switch the project to Linear colour space, because three.js r162 lights and blends colours in linear space.",
 ["Untick sRGB on every texture import, because three.js samples all of its textures and vertex colours as linear data.",
  "Use URP Unlit shaders everywhere, so Unity's lighting cannot shift the browser's colours.",
  "Convert every colour with `Color.gamma` before assigning it, which matches three.js's output encoding.",
  "Enable HDR on the camera and add ACES tonemapping, which three.js r162 applies to every frame by default."], 4),
("lambert_shader", "E03",
 "The browser game uses `MeshLambertMaterial` everywhere. In URP, the Lit shader (even at Smoothness 0, Metallic 0) multiplies diffuse by 0.96 and adds a specular environment term, so colours do not match. Which shader matches Lambert?",
 "URP Simple Lit with specular highlights off: Lambert diffuse plus emission, nothing else.",
 ["URP Lit at Smoothness 0 with Environment Reflections and Specular Highlights turned off on the material.",
  "URP Unlit, with the lighting baked into the colour by script at startup.",
  "URP Baked Lit, with the scene's lights baked into lightmaps for each level, which removes the extra terms.",
  "URP Complex Lit with clear coat disabled and the specular workflow selected."], 2),
("mirror_scene", "E04",
 "A three.js scene (z pointing south) is mirrored into Unity (z pointing north) by negating the z of every position. What else has to change?",
 "Rotations about x and y change sign, those about z keep theirs, and copied index buffers need reversed winding.",
 ["Rotations about z change sign, those about x and y keep theirs, and copied index buffers keep the winding three.js gave them.",
  "Nothing else: Unity converts handedness itself when a mesh or rotation is assigned from script.",
  "All three rotation angles change sign, and copied index buffers keep their winding unchanged.",
  "y and z must also be swapped, because Unity is y-up, and every rotation angle changes sign as well."], 1),
("unity_licence", "I03",
 "A Personal Unity licence was activated in Unity Hub on Windows. Copying its licence file into the Linux build container does not activate Unity there. Why?",
 "The licence file is bound to the hardware identifiers of the Windows machine that activated it.",
 ["Personal licences only cover the editor's own platform, so they cannot build Linux players.",
  "The licence file is encrypted with the Windows user's password and cannot be read under any other account.",
  "The container cannot reach Unity's licence server, which every start of the editor needs for a Personal licence.",
  "The licence file name must contain the exact editor version, which differs inside the container."], 0),
("signin_url", "I04",
 "A licence sign-in URL printed by a CLI in a narrow terminal was copied into a browser and failed with `invalid client_id`. Opening the same flow again and copying carefully failed the same way. Why, and what is the fix?",
 "The terminal's line wrap put a space into the copied URL; open the URL programmatically instead of copying it.",
 ["The client_id expires 60 seconds after it is printed; finish the whole sign-in within a minute of starting it.",
  "The URL is printed URL-encoded twice; decode it once before pasting it into the browser.",
  "The browser blocks the redirect to localhost; allow localhost redirects in its site settings and try again.",
  "The terminal converts `&` to `&amp;` when copying; replace the entities before pasting."], 3),
("timeout_ignored", "I08",
 "A headless Unity player started with GNU coreutils `timeout 8 ./Player.x86_64 -batchmode` ran for 70 minutes. Why, and what is the fix?",
 "The player ignored SIGTERM and timeout sends only one signal; use `timeout -k 5 8` to SIGKILL it later.",
 ["timeout counts CPU time, and an idle headless player uses almost none; use a wall-clock watchdog that kills it by pid.",
  "timeout cannot signal a process that calls setsid; run the player with `setsid -w` under timeout.",
  "timeout waited for a child the player had forked; run the player with `timeout --foreground` instead, which stops waiting.",
  "The signal waits for the player's next frame, which never comes in batch mode; add -nographics."], 2),
("pkill_self", "I09",
 "A coding agent ran `bash -c 'pkill -f \"node server.js 8123\"; ./smoke.sh'` to stop a game server between smoke tests. The agent's own shell was killed. Why, and what is the safer way?",
 "The pattern also matches the shell running pkill; stop the process listening on port 8123 (found with ss or lsof) instead.",
 ["pkill signals each match's whole process group, which included the shell; add --ns so that only the server process itself is signalled.",
  "With -f, pkill also matches environment variables, and the shell had exported the pattern; unset that variable first and run pkill again.",
  "node forwards SIGTERM to its parent process on exit; start the server with nohup so the signal stops there.",
  "pkill sends SIGHUP to the parent of every process it kills; run it with `trap '' HUP` set in the shell."], 4),
("headless_segfault", "J01",
 "A Unity 6.3 Linux player, started with `-batchmode -nographics` in a container without a display, segfaults at startup in `PlayerMain`; the log shows `Selected window backend: (null)`. What fixes it?",
 "Set `SDL_VIDEODRIVER=dummy`, so SDL has a video backend even with no display server.",
 ["Set `DISPLAY=:0`, so the player finds the host's X server, and mount /tmp/.X11-unix into the container.",
  "Install Mesa's llvmpipe, so the player gets software OpenGL instead of a GPU.",
  "Start the player with `-force-vulkan`, which has no window system dependency.",
  "Raise the stack size with `ulimit -s unlimited`, which PlayerMain needs at startup in headless mode."], 1),
("linux_receive_stall", "J04",
 "A Unity Linux player (Mono) stops receiving WebSocket messages for seconds at a time while the socket stays open; the Windows player is fine. A raw bash reader in the same container receives everything on time. The client uses `ClientWebSocket` and sends input while a `ReceiveAsync` is pending. What is the most likely cause and fix?",
 "Async reads stall while a write is in flight on the Linux runtime; read with blocking I/O on its own thread.",
 ["The container's network MTU is too small for WebSocket frames; raise the MTU of the Docker bridge network to match the host's.",
  "Nagle's algorithm holds back the server's small frames; set TCP_NODELAY on the server's sockets.",
  "The Linux kernel's receive buffers are too small; raise net.core.rmem_max and net.ipv4.tcp_rmem inside the container.",
  "The server sends larger snapshots to Linux clients; enable per-message deflate compression."], 3),
("float_rubberband", "B09",
 "The server simulates movement in integer fixed point (256 units per cell). The Unity client predicts the local player's movement with float math that is 'close enough'. Players see constant small rubber-banding. Why?",
 "Prediction must match the server step exactly; every snapshot corrects the drift, and each correction shows.",
 ["Float math is slower than integer math, so the client's prediction falls further behind the server every tick.",
  "The interpolation delay for remote players is too short, so their positions keep snapping.",
  "The server sends snapshots too rarely, so float prediction has too long to diverge between them.",
  "Unity's FixedUpdate runs at 50 Hz while the server runs at 20 Hz, so the prediction and server steps never line up."], 0),
("wire_codes", "L05",
 "The browser client turns local prediction on when the local player's state is alive. In the Unity port, a test that replays a captured real match reports 'predictor never active', though the player moves for 40 seconds. The port checks `(string)player[\"state\"] == \"alive\"` on the parsed snapshot JSON. What is the most likely cause?",
 "The wire carries a compact code (e.g. \"a\") that the browser decodes; the port compares it to the name.",
 ["The capture missed the join message, so the client never learns which player in the snapshot is its own.",
  "Coalesced snapshots skipped the one view in which the player's state changed to alive.",
  "Newtonsoft parses \"alive\" into an enum value, so the string comparison never matches.",
  "The predictor also needs the tick rate from the hello message, which the captured replay does not contain."], 2),
("css_border_tint", "F03",
 "A Unity uGUI port draws each panel's 2 px CSS border as a slightly larger Image in the border colour placed behind the face Image. The face is translucent (`rgba(0, 0, 0, 0.6)` in the CSS). In Unity the whole panel looks tinted with the border colour, unlike the browser. Why, and what fixes it?",
 "The border fill shows through the translucent face; draw the border as four edge strips instead.",
 ["uGUI blends in gamma space while CSS blends in linear; switch the Canvas to linear blending in the project settings.",
  "The face Image is maskable, so it inherits the border's colour; turn Maskable off on the face Image.",
  "The Canvas Scaler resamples the border into the face; switch it to Constant Pixel Size.",
  "CSS draws borders outside the box; set Preserve Aspect on the border Image to match."], 4),
("wsl_mirrored_localhost", "J03",
 "A game server runs inside WSL2 and binds 127.0.0.1:8080. The machine's `%UserProfile%\\.wslconfig` sets `networkingMode=mirrored`. A Windows-native Unity player must connect to that server. What works?",
 "Connect to 127.0.0.1:8080 from Windows; mirrored mode shares the host's loopback with WSL.",
 ["Bind the server to 0.0.0.0 and connect to the WSL VM's eth0 address; WSL loopback is private.",
  "Add a `netsh interface portproxy` rule from Windows 127.0.0.1:8080 to the WSL VM's address.",
  "Connect to `wsl.localhost:8080`, a name that resolves to the WSL VM from the Windows side.",
  "Open port 8080 in Windows Defender Firewall, which blocks loopback connections into WSL."], 1),
("mirror_audit", "E11",
 "A three.js ship is ported to Unity by mirroring z (Unity z = -three z): positions get z negated, rotations about x and y are negated, and every primitive mesh is built in Unity with three.js's own vertex formulas (cylinder vertex k at angle 2*PI*k/N as (r*sin, y, r*cos)). Screens match the browser, except some parts. Which parts are still wrong, and how are they fixed?",
 "Cylinders and cones with an odd side count are mirrored about their own axis; turn each 180 degrees about it.",
 ["Every box, because the z mirror reverses its face winding in Unity; reverse each box's triangle order when building it.",
  "Cylinders with an even side count, whose first vertex lands on the mirrored side; turn them by one facet.",
  "Only parts rotated about z, because the mirror also negates rotations about z; negate those angles.",
  "Spheres, because their UV seam ends up on the other side of the part; rotate each 180 degrees about y."], 3),
]

def h(qid, letter):
    return hashlib.sha256(f"gamedev_diag:{qid}:{letter}".encode()).hexdigest()

(ROOT / "questions").mkdir(parents=True, exist_ok=True)
(ROOT / "answers").mkdir(exist_ok=True)
(ROOT / "tests").mkdir(exist_ok=True)
key, ref = {}, {}
for qid, src, text, correct, wrong, pos in Q:
    assert len(wrong) == 4 and 0 <= pos <= 4
    options = wrong[:pos] + [correct] + wrong[pos:]
    body = f"# {qid}\n\n{text}\n\n" + "\n".join(f"{LETTERS[i]}. {o}" for i, o in enumerate(options)) + "\n"
    (ROOT / "questions" / f"{qid}.md").write_text(body)
    (ROOT / "answers" / f"{qid}.txt").write_text("?\n")
    key[qid] = h(qid, LETTERS[pos])
    ref[qid] = {"answer": LETTERS[pos], "source": f"unityworks specs/llm_evaluation_tasks.md {src}"}
(ROOT / "tests" / "answer_key.json").write_text(json.dumps(key, indent=1) + "\n")
(ROOT / "answers.reference.json").write_text(json.dumps(ref, indent=1) + "\n")
print(len(Q), sorted(r["answer"] for r in ref.values()))
