# force_push_clones

Build jobs clone from a bare repo on the build box with `git clone --shared` and record the commit they built. After a developer force-pushed a branch and a few days passed, rebuilding an old recorded commit fails with a missing-object error, although the commit was built fine before. Why, and what is the fix?

A. The clone is shallow by default when --shared is given, so old commits are never fetched; pass --no-shallow or --depth with a large number.
B. Shared clones borrow the source repo's object store; gc pruned the now-unreachable commits there. Set gc.auto 0 (or keep refs) in the bare repo.
C. Force-pushed commits are deleted from the bare repo immediately, so nothing can keep them; record the build's tree hash instead of the commit.
D. The job fetches only the branch heads, not the tags; fetch with --tags so that every commit that was ever built stays reachable for later rebuilds.
E. --shared clones break whenever the source repo is repacked; clone without --shared so that each build gets a full, independent object store.
