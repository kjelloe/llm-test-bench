# clone_unchecked

A build job runs `git clone "$REPO" lane/src; cd lane/src; git checkout "$COMMIT"; ./build.sh`. One night the clone failed (the server was down), yet the job reported success and published a build of last week's code. Why, and what is the fix?

A. git clone returns 0 even when the server is down if a local cache exists; pass --no-local so a network failure gives a non-zero exit status.
B. checkout fell back to the default branch when the commit was missing; use git switch --detach, which fails instead of guessing a branch.
C. build.sh used a cached artifact from the earlier run because its inputs looked unchanged; delete the build cache at the start of every job.
D. The clone's exit wasn't checked and an old lane/src survived, so checkout ran there; check every step and start each job in an empty lane.
E. The job ran under set -e, but a cd inside a script resets the option; move the set -e line below the cd so it still applies to the build.
