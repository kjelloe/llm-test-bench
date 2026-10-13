# rid_lockfile_dirty

Builds publish each game with `-r linux-x64` and `-r win-x64` and stamp the version from `git describe --dirty`. The games reference a shared library project that has RestorePackagesWithLockFile on. Every build after the first is stamped -dirty, though nobody edited anything. Why, and what is the fix?

A. The version is stamped before restore, so restore's file timestamps count as edits; move the stamping step after the publish.
B. Lock files record the machine's NuGet cache path; add packages.lock.json to .gitignore so that builds stop seeing it change.
C. Each per-RID publish adds a RID section to the library's packages.lock.json; give the library the same RuntimeIdentifiers and commit it.
D. NuGet floats patch versions on every restore; pin each package to an exact [x.y.z] version in the library's project file.
E. Windows publish writes CRLF line endings into the lock file; set core.autocrlf on the build box so that git ignores the difference in that file.
