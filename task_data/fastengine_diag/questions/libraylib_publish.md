# libraylib_publish

A C# game client on Raylib-cs runs fine with `dotnet run`. The Linux build was made with `dotnet publish -c Release -o out` (no runtime identifier). Started on a clean Linux machine it fails with `DllNotFoundException: Unable to load shared library 'raylib'`; on the developer's machine it works only after libraylib.so was copied next to the binary by hand. What is the fix?

A. Add a launcher script that sets LD_LIBRARY_PATH to the folder holding libraylib.so before it starts the client, and ship the .so in the zip.
B. Install raylib from the distribution's package manager on every target machine, since Raylib-cs only binds to a system-wide copy of the library.
C. Publish for the runtime (`-r linux-x64 --self-contained`), so the package's runtimes/linux-x64/native library is placed beside the binary.
D. Publish with NativeAOT, which links the native raylib library statically into the single executable so nothing needs to be found at run time.
E. Copy libraylib.so into /usr/local/lib and run ldconfig in the install step, which is where .NET's DllImport looks for native libraries.
