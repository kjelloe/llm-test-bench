# ws_abort

A Unity client's receive loop is:

```csharp
try { var r = await ws.ReceiveAsync(buffer, shutdown); /* ... */ }
catch (OperationCanceledException) { return; } // shutting down
catch (WebSocketException e) { OnClosed(e.Message); Reconnect(); }
```

To simulate a network drop a tester calls `ws.Abort()` on the `ClientWebSocket` while a receive is pending. The connection goes silent and no reconnect ever happens. Why, and what is the fix?

A. Abort() leaves the pending ReceiveAsync waiting for the server's FIN; call CloseAsync instead, which completes the pending receive at once and runs the reconnect path.
B. The aborted receive throws OperationCanceledException, which this loop takes for shutdown; only treat it as shutdown when the `shutdown` token is cancelled.
C. The WebSocketException is raised on a thread-pool thread that Unity swallows; marshal it to the main thread before calling Reconnect.
D. Abort() makes ReceiveAsync return a Close message with Count 0 that the elided code ignores; check MessageType for Close first.
E. Abort() also cancels the `shutdown` token passed to ReceiveAsync; pass a fresh CancellationToken.None to every receive and keep the shutdown token for the loop only.
