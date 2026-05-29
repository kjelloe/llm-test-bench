### Re-creation brief for a local coding AI

If I were describing **1982’s *Paratrooper*** to a local AI so it could rebuild it in JavaScript or Python, I’d frame it like this:

```text
Re-create a faithful, clean-room version of the 1982 game "Paratrooper" as a retro CGA-style fixed shooter.

Core concept:
- The entire game takes place on a single screen.
- The player controls a stationary anti-aircraft gun turret positioned at the bottom center of the screen.
- The turret cannot move left or right, but it can rotate to aim across a wide arc.
- The player fires shells upward at airborne enemies and falling infantry.

Main enemies and threats:
1. Helicopters
   - Helicopters fly horizontally across the screen from left-to-right or right-to-left.
   - They appear at different heights.
   - Their main behavior is to periodically drop paratroopers.

2. Paratroopers
   - After being dropped, paratroopers descend slowly under parachutes.
   - If the paratrooper himself is hit directly, he dies immediately.
   - If only the parachute is hit, the paratrooper loses the chute and falls rapidly to the ground.
   - A falling body can kill other paratroopers it lands on.
   - If a paratrooper reaches the ground safely, he counts as a successful landing on either the left side or right side of the turret, depending on where he landed.

3. Jets
   - Faster aircraft occasionally cross the screen.
   - Jets can be shot down.
   - Their special action is dropping bombs toward the turret.

4. Bombs
   - Bombs fall toward the ground after being dropped by jets.
   - Bombs can be shot and destroyed before impact.
   - If a bomb hits the player’s turret, the game ends immediately.

Loss conditions:
- Immediate loss if a bomb hits the turret.
- Also lose if 4 paratroopers safely land on the same side of the turret (4 on the left OR 4 on the right, not 4 total).
- When 4 accumulate on one side, they form a human pyramid / climb up and destroy the turret. That should be shown as a short defeat animation or sequence.

Scoring:
- Award points for destroying helicopters, paratroopers, jets, and bombs.
- Important rule: every shot fired costs 1 point.
- This means blind shooting reduces score and creates a risk/reward ammo discipline mechanic.

Player controls:
- Rotate turret left
- Rotate turret right
- Fire
- Optional pause / restart

Gameplay feel:
- Fast, simple, tense, and readable.
- Single-screen arcade gameplay with increasing pressure over time.
- The challenge comes from prioritizing threats:
  - helicopters create more paratroopers,
  - parachutes and falling bodies create chain reactions,
  - jets and bombs are immediate high-priority threats,
  - letting too many paratroopers land on one side causes defeat.

Visual style:
- Emulate early IBM PC / CGA-era presentation:
  - low resolution feel,
  - limited color palette,
  - simple sprite silhouettes,
  - black sky background,
  - bright projectiles and explosions,
  - minimal HUD.
- Do not aim for modern particle-heavy visuals; aim for crisp retro readability.
- Use simple, exaggerated sprite states so the player can clearly tell:
  - helicopter,
  - jet,
  - bomb,
  - parachuting soldier,
  - falling soldier,
  - landed soldier stack,
  - turret hit / explosion.

Audio:
- Very simple retro sound effects:
  - shot,
  - explosion,
  - parachute hit,
  - bomb drop / bomb explode,
  - defeat.
- Optional intro tune inspired by the famous Bach-like PC-speaker intro feel, but use original audio assets or newly generated audio rather than copying.

Implementation structure:
- Build it as a deterministic 2D arcade game using a fixed timestep update loop.
- Recommended options:
  - JavaScript: HTML5 Canvas in browser
  - Python: Pygame
- Organize game logic with simple entity classes or structs:
  - PlayerTurret
  - Projectile
  - Helicopter
  - Jet
  - Bomb
  - Paratrooper
  - Explosion
  - GameState / WaveManager / ScoreSystem

Required entity states:
- Paratrooper:
  - descending_with_parachute
  - free_fall
  - landed_left
  - landed_right
  - dead
- Aircraft:
  - entering
  - active
  - destroyed
  - exiting
- Turret:
  - alive
  - destroyed

Physics / behavior:
- Player shots travel in the direction of the barrel.
- Helicopters and jets move horizontally.
- Bombs fall downward.
- Paratroopers descend slowly while parachuting and quickly in free-fall.
- Collisions should be forgiving and arcade-like, not realistic simulation.
- Prioritize gameplay clarity over realism.

Game loop:
1. Show title / start screen
2. Start single-screen action
3. Spawn helicopters regularly
4. Drop paratroopers from helicopters
5. Occasionally spawn jets that drop bombs
6. Update score and landed troop counts
7. Increase difficulty gradually by tuning spawn rate, aircraft speed, or bomb frequency
8. End on turret destruction or 4 landed troops on one side
9. Show final score and restart option

Difficulty scaling:
- Gradually increase pressure over time.
- Possible tuning knobs:
  - more helicopters,
  - faster helicopters,
  - more frequent paratrooper drops,
  - more frequent jet appearances,
  - faster bomb drops.
- Keep it fair: the player should always have a chance to recover with good aim.

HUD:
- Score
- Maybe current landed count on left and right
- Optional lives should be omitted if aiming for faithfulness; original feel is one-base survival.

Polish details:
- Show explosions when aircraft or bombs are destroyed.
- Show splat / impact animation for free-falling paratroopers.
- Show visible accumulation of landed troops on each side.
- Show a brief climb-and-destroy sequence when 4 troops land on one side.
- Keep menus and UI very minimal.

Important design goal:
This is not a scrolling shooter and not a tower defense game. It is a fixed-screen defense game about aim, prioritization, and preventing buildup on either side of a central turret.

Deliverables:
- A runnable game
- Clean, readable source code
- Simple placeholder sprites generated in code or as basic pixel art
- No copyrighted original assets required
- Configuration constants for tuning spawn rates, scores, speeds, and collision sizes
```

### Expert notes I’d add for accuracy

#### What matters most
The **heart of the game** is this tension:

- shoot helicopters to reduce future threats,
- shoot paratroopers before they land,
- shoot parachutes to convert a slow problem into a fast falling projectile,
- react quickly to jets and bombs,
- avoid wasting shots because shots cost points.

That last rule — **every shell costs 1 point** — is part of what makes the original feel different from a generic arcade shooter.

#### What not to overcomplicate
A remake should stay simple:

- one screen,
- one turret,
- no inventory,
- no power-ups,
- no campaign map,
- no physics sandbox,
- no modern UI clutter.

#### What can be tuned
Some details in old games vary slightly between ports/remakes and are best tuned by feel:

- exact turret rotation speed,
- exact projectile speed,
- exact helicopter spawn cadence,
- exact jet frequency,
- exact score values,
- exact collision boxes.

So I’d tell the AI to treat those as **configurable constants**, not hard-coded truths.

### Best source references
For authenticity, I’d use the gameplay summary from [Wikipedia] which is below:

```
Gameplay
The player controls a gun turret at the bottom of the screen. The turret can swivel to cover a large area of the screen, but cannot move from its base. Helicopters fly across the screen at varying heights, dropping paratroopers. The gun may fire multiple shots at once, and the shots may destroy helicopters or shoot paratroopers. Paratroopers may be disintegrated by a direct hit, or their parachutes may be shot, in which case they will plummet to earth (splattering and dying, killing any paratrooper onto whom they fall). Periodically, jets may fly by and drop bombs; the jets and bombs may be shot as well.

The player earns points by shooting helicopters, paratroopers, jets, and bombs. Firing a shell costs the player one point, so if one is playing for score, there is an incentive to conserve ammo.

The game ends when the player's turret is hit by a bomb, or when four paratroopers safely land on either the left or right of the turret (that is four on one side, not four total). Once this happens, they are able to build a human pyramid and climb up to the turret and blow it up.


Paratrooper
"Paratrooper intro"
Duration: 7 seconds.0:07
Paratrooper video game intro music, as played through the PC Speakers.
Problems playing this file? See media help.
The game's intro music is an interpretation of a brief section of Johann Sebastian Bach's Toccata and Fugue in D minor, BWV 565, played through the PC speaker.[2]

Reception
PC Magazine gave Paratrooper 10 points out of 18. The magazine described it as "a well-executed but unexceptional game [which] quickly loses its appeal after a dozen or so plays".[2] In 1984 Softline readers named Paratrooper the worst IBM program of 1983.[3]
```


