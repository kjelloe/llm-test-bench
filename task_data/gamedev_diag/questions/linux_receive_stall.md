# linux_receive_stall

A Unity Linux player (Mono) stops receiving WebSocket messages for seconds at a time while the socket stays open; the Windows player is fine. A raw bash reader in the same container receives everything on time. The client uses `ClientWebSocket` and sends input while a `ReceiveAsync` is pending. What is the most likely cause and fix?

A. The container's network MTU is too small for WebSocket frames; raise the MTU of the Docker bridge network to match the host's.
B. Nagle's algorithm holds back the server's small frames; set TCP_NODELAY on the server's sockets.
C. The Linux kernel's receive buffers are too small; raise net.core.rmem_max and net.ipv4.tcp_rmem inside the container.
D. Async reads stall while a write is in flight on the Linux runtime; read with blocking I/O on its own thread.
E. The server sends larger snapshots to Linux clients; enable per-message deflate compression.
