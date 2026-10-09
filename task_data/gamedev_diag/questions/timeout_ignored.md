# timeout_ignored

A headless Unity player started with `timeout 8 ./Player.x86_64 -batchmode` ran for 70 minutes. Why, and what is the fix?

A. timeout counts CPU time, and an idle headless player uses almost none; use a wall-clock watchdog that kills it by pid.
B. timeout cannot signal a process that calls setsid; run the player with `setsid -w` under timeout.
C. The player ignored SIGTERM and timeout sends only one signal; use `timeout -k 5 8` to SIGKILL it later.
D. timeout waited for a child the player had forked; run the player with `timeout --foreground` instead, which stops waiting.
E. The signal waits for the player's next frame, which never comes in batch mode; add -nographics.
