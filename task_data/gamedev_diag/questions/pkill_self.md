# pkill_self

A coding agent ran `bash -c 'pkill -f "node server.js 8123"; ./smoke.sh'` to stop a game server between smoke tests. The agent's own shell was killed. Why, and what is the safer way?

A. pkill signals each match's whole process group, which included the shell; add --ns so that only the server process itself is signalled.
B. With -f, pkill also matches environment variables, and the shell had exported the pattern; unset that variable first and run pkill again.
C. node forwards SIGTERM to its parent process on exit; start the server with nohup so the signal stops there.
D. pkill sends SIGHUP to the parent of every process it kills; run it with `trap '' HUP` set in the shell.
E. The pattern also matches the shell running pkill; stop the process listening on port 8123 (found with ss or lsof) instead.
