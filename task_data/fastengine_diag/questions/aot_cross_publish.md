# aot_cross_publish

A Linux build box must produce the win-x64 client of a .NET 9 game on Raylib-cs. A developer proposes `dotnet publish -r win-x64 -p:PublishAot=true` for a single fast exe, and adds the Visual C++ redistributable to the zip in case raylib.dll needs it. What should the job do?

A. Use NativeAOT as proposed, but install the Windows SDK's link.exe under Wine on the build box so the cross-compile can find a Windows linker.
B. Publish self-contained without AOT, as NativeAOT can't cross-compile from Linux; check raylib.dll's imports: static CRT needs no VC++.
C. Publish framework-dependent to keep the zip small, and ship the .NET 9 desktop runtime installer next to the exe for players who lack it.
D. Build on the Linux box with -r win-x64 and ReadyToRun only; AOT is fine later, but VC++ must always ship because every native DLL needs it.
E. Keep AOT and switch the job to a Windows runner; the VC++ redistributable is required either way, since raylib.dll is a C library.
