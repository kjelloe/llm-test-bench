# winexe_lcid

A .NET 9 client (OutputType WinExe, InvariantGlobalization on) picks its UI language at start-up with `CultureInfo.GetCultureInfo(GetUserDefaultLCID())`. On a player's en-GB Windows PC the window opens and closes at once; the Linux build and the developer's en-US Windows runs are fine. Why, and what is the fix?

A. en-GB is missing from the game's translation table, so the lookup returns null and the HUD crashes; add an en-GB entry.
B. WinExe programs need the Visual C++ runtime, which that PC lacks; ship the redistributable installer inside the zip.
C. A WinExe has no console, so the process exits once Main returns; change OutputType to Exe to keep the window alive.
D. raylib's GL 3.3 context fails on that PC's graphics driver; fall back to OpenGL ES through ANGLE whenever creating the context fails.
E. With invariant globalization .NET can't resolve an LCID such as 0x0809 and throws; ask Windows for the name (LCIDToLocaleName).
