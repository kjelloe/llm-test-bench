# headless_segfault

A Unity 6.3 Linux player, started with `-batchmode -nographics` in a container without a display, segfaults at startup in `PlayerMain`; the log shows `Selected window backend: (null)`. What fixes it?

A. Set `DISPLAY=:0`, so the player finds the host's X server, and mount /tmp/.X11-unix into the container.
B. Set `SDL_VIDEODRIVER=dummy`, so SDL has a video backend even with no display server.
C. Install Mesa's llvmpipe, so the player gets software OpenGL instead of a GPU.
D. Start the player with `-force-vulkan`, which has no window system dependency.
E. Raise the stack size with `ulimit -s unlimited`, which PlayerMain needs at startup in headless mode.
