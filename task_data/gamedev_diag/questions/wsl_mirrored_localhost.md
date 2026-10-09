# wsl_mirrored_localhost

A game server runs inside WSL2 and binds 127.0.0.1:8080. The machine's `%UserProfile%\.wslconfig` sets `networkingMode=mirrored`. A Windows-native Unity player must connect to that server. What works?

A. Bind the server to 0.0.0.0 and connect to the WSL VM's eth0 address; WSL loopback is private.
B. Connect to 127.0.0.1:8080 from Windows; mirrored mode shares the host's loopback with WSL.
C. Add a `netsh interface portproxy` rule from Windows 127.0.0.1:8080 to the WSL VM's address.
D. Connect to `wsl.localhost:8080`, a name that resolves to the WSL VM from the Windows side.
E. Open port 8080 in Windows Defender Firewall, which blocks loopback connections into WSL.
