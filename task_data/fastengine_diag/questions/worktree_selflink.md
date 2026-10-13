# worktree_selflink

Two coding agents work in parallel git worktrees of the engine. Each runs `ln -s ~/GIT/<game> ../<game>` for every game so its build finds the game repos next to the engine, as the docs say. Afterwards every build of every game is stamped -dirty (from `git describe --dirty` in the game repo), though nobody edited the games. Why, and what is the fix?

A. Worktrees share one index with the main checkout, so one agent's staged files show up as edits in the others; use separate clones.
B. The second ln -s found the link in place and made one inside its target, a self-link in each game repo; delete it, use ln -sfn.
C. git describe runs in the engine worktree, which counts the new symlinks as untracked files; add the links to the engine's .gitignore.
D. Symlinked repos leave git's stat cache stale, so every file looks changed; run git update-index --refresh before stamping.
E. Both agents' builds wrote obj/ folders into the game repos at once; add obj/ and bin/ to each game repo's .gitignore.
