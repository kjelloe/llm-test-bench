# corrections_noise

A scripted 60-second play smoke reports 3 client-prediction corrections on the win64 build and 0 on linux64, same script and same server. The simulation is integer fixed-point (256 units per cell). Bug or noise, and how do you tell?

A. Measure their size and rate: small corrections (well under a cell) at a steady low rate are timing jitter; a logic drift would grow over time.
B. Any correction on fixed-point maths is a bug, because the simulation is deterministic; fail the win64 smoke until the corrections reach zero.
C. It is the .NET JIT producing different floating-point results on Windows; switch the predictor to decimal arithmetic on both platforms.
D. It is Windows' 15.6 ms default timer resolution; call timeBeginPeriod(1) at start-up, after which the two builds will report the same.
E. Three in a minute is under the smoke's noise threshold; raise the threshold to five and stop measuring corrections on either of the two builds.
