# clean_windows_gap

The self-contained win-x64 zip of a raylib client (static CRT) starts on every developer PC. A tester runs it on a fresh Windows 11 VM reached over Remote Desktop and the window never appears; the log ends right after start-up. What is the most likely missing piece?

A. An OpenGL 3.3 driver: VMs and RDP often expose only Microsoft's GL 1.1 GDI renderer, so context creation fails; install or pass one in.
B. The .NET 9 desktop runtime, which a self-contained publish still needs on the target for the WinForms parts that raylib's window uses.
C. The Visual C++ 2015-2022 redistributable, because raylib.dll links the C runtime dynamically in every official release, static or not.
D. Smart App Control blocking the unsigned exe silently; it never shows a dialog for zip-extracted files, so the window just doesn't appear.
E. DirectX 12 runtime components, which Windows 11 VMs omit by default and raylib uses for its window surface even when it renders with GL.
