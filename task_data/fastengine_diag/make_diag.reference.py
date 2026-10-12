"""Generates task_data/fastengine_diag (questions, stub answers, hashed key) from fastengine's
specs/llm_evaluation_tasks.md (2026-10-12). Contains the answers, so the .reference name keeps it out of
--export-task. Usage: python3 make_diag.reference.py task_data/fastengine_diag"""
import hashlib, json, sys
from pathlib import Path

ROOT = Path(sys.argv[1])
LETTERS = "ABCDE"
SALT = "fastengine_diag"
# (id, spec ref, question, correct option, [distractors], position of the correct option 0-4)
Q = [
("libraylib_publish", "A03",
 "A C# game client on Raylib-cs runs fine with `dotnet run`. The Linux build was made with `dotnet publish -c Release -o out` (no runtime identifier). Started on a clean Linux machine it fails with `DllNotFoundException: Unable to load shared library 'raylib'`; on the developer's machine it works only after libraylib.so was copied next to the binary by hand. What is the fix?",
 "Publish for the runtime (`-r linux-x64 --self-contained`), so the package's runtimes/linux-x64/native library is placed beside the binary.",
 ["Add a launcher script that sets LD_LIBRARY_PATH to the folder holding libraylib.so before it starts the client, and ship the .so in the zip.",
  "Install raylib from the distribution's package manager on every target machine, since Raylib-cs only binds to a system-wide copy of the library.",
  "Publish with NativeAOT, which links the native raylib library statically into the single executable so nothing needs to be found at run time.",
  "Copy libraylib.so into /usr/local/lib and run ldconfig in the install step, which is where .NET's DllImport looks for native libraries."], 2),
("fill_culling", "A05",
 "fastengine's canvas-2D port fills a path by triangulating it and drawing the triangles through raylib's rlgl batch, between the 3D scene and the rest of the HUD. Paths whose points run counter-clockwise on screen fill correctly; the same shapes drawn clockwise do not show at all. Why, and what is the fix?",
 "rlgl's batch has back-face culling on, so one winding is culled; flush the batch, draw the fill with culling off, flush again, then turn culling back on.",
 ["The ear-clipping triangulation assumes counter-clockwise input and emits nothing for clockwise rings; detect the ring's orientation and handle both cases there.",
  "The HUD's camera has Y pointing down, which mirrors every triangle on screen; render the HUD with a Y-up orthographic camera like the 3D scene uses.",
  "The depth test is still on from the 3D pass and the clockwise fills land behind the scene; clear the depth buffer before the HUD layer is drawn.",
  "The fill colour's alpha is premultiplied twice for clockwise paths, making them transparent; convert colours to straight alpha before drawing."], 0),
("mirror_target", "B09",
 "A port renders a water reflection by drawing the scene from a mirrored camera into a render target with the same pipeline as the screen (ACES tone mapping and sRGB encoding applied), then samples that target in the water shader, whose own output is tone mapped and encoded again. The reflection looks washed out and too bright next to the browser. Why, and what is the fix?",
 "three renders into targets linear and untoned; draw the mirror pass without tone mapping or encoding, so the reflection is encoded once at the end.",
 ["The target's texture is sampled as linear although it holds sRGB values; give it an sRGB format so sampling decodes it before the water shader uses it.",
  "The render target is 8-bit and clips the reflection's highlights; switch it to a half-float format so values above one survive until tone mapping.",
  "The mirrored camera has no oblique near plane, so geometry under the water leaks into the reflection; clip the projection at the water plane.",
  "Mipmaps are generated for the reflection target and blur it into a brighter haze; turn off mipmap generation and sample the target with point filtering."], 4),
("rt_premultiplied", "B14",
 "A HUD minimap is rendered into a render target cleared to transparent black, using normal alpha blending for everything drawn into it. The target's texture is then drawn onto the HUD, also with normal alpha blending (SRC_ALPHA, ONE_MINUS_SRC_ALPHA). Its soft edges get dark borders and dark halos that the browser does not show. Why, and what is the fix?",
 "Blending into the transparent target leaves premultiplied colour in its texels; draw the texture with ONE, ONE_MINUS_SRC_ALPHA instead.",
 ["Bilinear filtering mixes the transparent black border texels into the soft edge pixels; switch the target's texture to point filtering instead.",
  "The target is cleared to black, which shows through every partly transparent pixel; clear it to the HUD panel's own colour instead.",
  "The target's colour attachment is stored in sRGB and decoded twice on the way to the screen; create it with a linear colour format.",
  "The minimap is drawn upside down and the edge pixels sample the wrong row; flip the texture coordinates on Y when drawing the target."], 3),
("port_browser", "C04",
 "The Unity port of a game interpolates between server snapshots. The browser client draws the newest snapshot as soon as it arrives. A new fastengine port copied the Unity port's interpolator; its ships move more smoothly but lag the browser in side-by-side shots. What should the fastengine port do?",
 "Port the browser: draw the newest view as it arrives and leave the interpolator unused. The browser is the reference, not another port.",
 ["Keep the interpolator, which is the better design, and ask the game team to add the same interpolation to the browser so the clients match.",
  "Keep interpolating but shorten its delay to a single server tick, so the lag behind the browser falls below what a screenshot can show.",
  "Replace interpolation with extrapolation from the last two views, which removes the lag while keeping the smoother motion it gave.",
  "Leave it as it is and record the difference as accepted, because both clients show the same server state within a tick of each other."], 1),
("font_fallback", "C09",
 "A browser reference screenshot (headless Chromium on a Linux build box) shows the HUD's `font-family: \"Courier New\", monospace` text heavier and wider than the fastengine client, which maps Courier New to Liberation Mono. The client's font metrics were already checked against the TTF tables. Why do they differ?",
 "The build box lacks Liberation, so Chromium fell back to DejaVu Sans Mono; the difference is the reference shot's font, not the client's.",
 ["Chromium scales CSS sizes by the font's unitsPerEm while the client scales by the raster size, so the client's text is about 7% too small.",
  "Headless Chromium synthesises bold for monospace fonts at small sizes; launch it with --disable-font-subpixel-positioning to match.",
  "The build box runs Chromium at a device scale factor of 1.25, enlarging all text; pass --force-device-scale-factor=1 to the shot.",
  "Chromium applies full hinting while raylib draws unhinted glyphs, which thickens the strokes; switch the client to FreeType's hinting."], 4),
("smart_app_control", "F05",
 "A job-built, unsigned win64 build of the client is blocked by Smart App Control on the Windows 11 test PC (no \"run anyway\" button). A dev build of the same code ran there yesterday. The agent plans to retry with a fresh build, an `Unblock-File`, and a copy under a different path. What is right?",
 "SAC's verdict on unsigned binaries varies and cannot be overridden; the only fix is signing. Stop retrying: each try pops up on the user's desktop.",
 ["The zip carries the Mark of the Web from the download; Unblock-File on the zip before extracting clears it, after which Smart App Control allows the exe.",
  "Rebuild deterministically so the exe is byte-identical to yesterday's dev build, whose hash Smart App Control has already accepted on that machine.",
  "Add the build folder to Microsoft Defender's exclusion list, which Smart App Control also honours for files that are not signed.",
  "Start it from the WSL side through interop, which bypasses Smart App Control because the process is launched by a Linux parent."], 2),
("corrections_noise", "G09",
 "A scripted 60-second play smoke reports 3 client-prediction corrections on the win64 build and 0 on linux64, same script and same server. The simulation is integer fixed-point (256 units per cell). Bug or noise, and how do you tell?",
 "Measure their size and rate: small corrections (well under a cell) at a steady low rate are timing jitter; a logic drift would grow over time.",
 ["Any correction on fixed-point maths is a bug, because the simulation is deterministic; fail the win64 smoke until the corrections reach zero.",
  "It is the .NET JIT producing different floating-point results on Windows; switch the predictor to decimal arithmetic on both platforms.",
  "It is Windows' 15.6 ms default timer resolution; call timeBeginPeriod(1) at start-up, after which the two builds will report the same.",
  "Three in a minute is under the smoke's noise threshold; raise the threshold to five and stop measuring corrections on either of the two builds."], 0),
("force_push_clones", "H04",
 "Build jobs clone from a bare repo on the build box with `git clone --shared` and record the commit they built. After a developer force-pushed a branch and a few days passed, rebuilding an old recorded commit fails with a missing-object error, although the commit was built fine before. Why, and what is the fix?",
 "Shared clones borrow the source repo's object store; gc pruned the now-unreachable commits there. Set gc.auto 0 (or keep refs) in the bare repo.",
 ["The clone is shallow by default when --shared is given, so old commits are never fetched; pass --no-shallow or --depth with a large number.",
  "Force-pushed commits are deleted from the bare repo immediately, so nothing can keep them; record the build's tree hash instead of the commit.",
  "The job fetches only the branch heads, not the tags; fetch with --tags so that every commit that was ever built stays reachable for later rebuilds.",
  "--shared clones break whenever the source repo is repacked; clone without --shared so that each build gets a full, independent object store."], 1),
("systemd_expand", "H08",
 "A worker starts a job with `systemd-run --wait --pipe sh -c 'printf \"%s\\n\" \"${X-unset}\"'`, with X set in the unit's environment (systemd 259). It prints an empty line instead of X's value, although the same `sh -c` command works in a shell. Why, and what is the fix?",
 "systemd-run itself expands $VAR and ${VAR…} in the command line before sh ever sees it; pass --expand-environment=no, or escape each as $$.",
 ["The unit does not inherit the caller's environment; pass the value explicitly with --setenv=X so that the sh started by the unit can see it.",
  "systemd runs the command under /bin/sh, which is dash on this box and lacks the ${X-default} form; use bash -c for the command instead.",
  "--pipe connects the command's output to the caller only after it exits, which drops output written before; use --pty instead of --pipe.",
  "The single quotes are consumed by systemd's own parser, so printf gets its format split across arguments; double the quoting to compensate."], 3),
]


def h(qid, letter):
    return hashlib.sha256(f"{SALT}:{qid}:{letter}".encode()).hexdigest()


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
    ref[qid] = {"answer": LETTERS[pos], "source": f"fastengine specs/llm_evaluation_tasks.md {src}"}
(ROOT / "tests" / "answer_key.json").write_text(json.dumps(key, indent=1) + "\n")
(ROOT / "answers.reference.json").write_text(json.dumps(ref, indent=1) + "\n")
print(len(Q), sorted(r["answer"] for r in ref.values()))
