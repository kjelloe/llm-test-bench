using System;

namespace GameClient
{
    // The Unity client's helm and selection commands: a port of CarrierDominion's js/helm.mjs (verbatim
    // from client/main.js). Same guards, clamps and payloads, so the server sees exactly what the browser
    // sends.
    public sealed class Helm
    {
        public Helm(Action<Command> send) => throw new NotImplementedException();

        public int CarrierId => throw new NotImplementedException();
        public int Throttle => throw new NotImplementedException();
        public int Rudder => throw new NotImplementedException();
        public int Climb => throw new NotImplementedException();
        public int SelectedUnitId => throw new NotImplementedException();
        public bool Piloting => throw new NotImplementedException();

        public void OnSnapshot(HelmView view) => throw new NotImplementedException();  // onSnapshot
        public void ThrottleUp() => throw new NotImplementedException();               // key w
        public void ThrottleDown() => throw new NotImplementedException();             // key s
        public void Stop() => throw new NotImplementedException();                     // key x
        public void SendRudder(int next) => throw new NotImplementedException();
        public void SendClimb(int next) => throw new NotImplementedException();
        public void CycleSelection() => throw new NotImplementedException();
        public void Launch(int kind) => throw new NotImplementedException();
        public void OrderEscort() => throw new NotImplementedException();
        public void RecallSelected() => throw new NotImplementedException();
        public void TogglePiloting() => throw new NotImplementedException();
    }
}
