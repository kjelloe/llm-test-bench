# systemd_expand

A worker starts a job with `systemd-run --wait --pipe sh -c 'printf "%s\n" "${X-unset}"'`, with X set in the unit's environment (systemd 259). It prints an empty line instead of X's value, although the same `sh -c` command works in a shell. Why, and what is the fix?

A. The unit does not inherit the caller's environment; pass the value explicitly with --setenv=X so that the sh started by the unit can see it.
B. systemd runs the command under /bin/sh, which is dash on this box and lacks the ${X-default} form; use bash -c for the command instead.
C. --pipe connects the command's output to the caller only after it exits, which drops output written before; use --pty instead of --pipe.
D. systemd-run itself expands $VAR and ${VAR…} in the command line before sh ever sees it; pass --expand-environment=no, or escape each as $$.
E. The single quotes are consumed by systemd's own parser, so printf gets its format split across arguments; double the quoting to compensate.
