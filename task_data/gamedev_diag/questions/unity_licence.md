# unity_licence

A Personal Unity licence was activated in Unity Hub on Windows. Copying its licence file into the Linux build container does not activate Unity there. Why?

A. The licence file is bound to the hardware identifiers of the Windows machine that activated it.
B. Personal licences only cover the editor's own platform, so they cannot build Linux players.
C. The licence file is encrypted with the Windows user's password and cannot be read under any other account.
D. The container cannot reach Unity's licence server, which every start of the editor needs for a Personal licence.
E. The licence file name must contain the exact editor version, which differs inside the container.
