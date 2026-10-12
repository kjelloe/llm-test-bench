# port_browser

The Unity port of a game interpolates between server snapshots. The browser client draws the newest snapshot as soon as it arrives. A new fastengine port copied the Unity port's interpolator; its ships move more smoothly but lag the browser in side-by-side shots. What should the fastengine port do?

A. Keep the interpolator, which is the better design, and ask the game team to add the same interpolation to the browser so the clients match.
B. Port the browser: draw the newest view as it arrives and leave the interpolator unused. The browser is the reference, not another port.
C. Keep interpolating but shorten its delay to a single server tick, so the lag behind the browser falls below what a screenshot can show.
D. Replace interpolation with extrapolation from the last two views, which removes the lag while keeping the smoother motion it gave.
E. Leave it as it is and record the difference as accepted, because both clients show the same server state within a tick of each other.
