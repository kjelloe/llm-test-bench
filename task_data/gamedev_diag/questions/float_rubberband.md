# float_rubberband

The server simulates movement in integer fixed point (256 units per cell). The Unity client predicts the local player's movement with float math that is 'close enough'. Players see constant small rubber-banding. Why?

A. Prediction must match the server step exactly; every snapshot corrects the drift, and each correction shows.
B. Float math is slower than integer math, so the client's prediction falls further behind the server every tick.
C. The interpolation delay for remote players is too short, so their positions keep snapping.
D. The server sends snapshots too rarely, so float prediction has too long to diverge between them.
E. Unity's FixedUpdate runs at 50 Hz while the server runs at 20 Hz, so the prediction and server steps never line up.
