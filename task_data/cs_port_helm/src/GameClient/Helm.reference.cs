using System;
using System.Collections.Generic;
using System.Linq;

namespace GameClient
{
    // The Unity client's helm and selection commands: a port of CarrierDominion's js/helm.mjs (verbatim
    // from client/main.js). Same guards, clamps and payloads, so the server sees exactly what the browser
    // sends.
    public sealed class Helm
    {
        const int ThrottleStep = 10;
        const int KindManta = 0, KindWalrus = 1;
        const int UnitActive = 1, UnitReturning = 2, UnitLanded = 4;

        readonly Action<Command> _send;
        HelmView _view;

        public Helm(Action<Command> send) => _send = send;

        public int CarrierId { get; private set; } = -1;
        public int Throttle { get; private set; }
        public int Rudder { get; private set; }
        public int Climb { get; private set; }
        public int SelectedUnitId { get; private set; } = -1;
        public bool Piloting { get; private set; }

        List<UnitView> AfloatUnits() => _view == null
            ? new List<UnitView>()
            : _view.Units.Where(u => u.Team == _view.Team && (u.State == UnitActive || u.State == UnitReturning || u.State == UnitLanded)).ToList();

        List<UnitView> SelectableUnits() => AfloatUnits().Where(u => u.Kind == KindManta || u.Kind == KindWalrus).ToList();

        UnitView SelectedUnit() => AfloatUnits().FirstOrDefault(u => u.Id == SelectedUnitId);

        static CarrierView OwnCarrierOf(HelmView view) => view.Carriers.FirstOrDefault(c => c.Team == view.Team && c.Contact == 0);

        static int ClampThrottle(int value, int floor) => Math.Max(floor, Math.Min(100, value));

        public void OnSnapshot(HelmView view)
        {
            _view = view;
            CarrierView own = OwnCarrierOf(view);
            if (own != null)
            {
                CarrierId = own.Id;
                if (!Piloting)
                {
                    Throttle = own.Throttle;
                    Rudder = own.Rudder;
                }
            }
            if (SelectedUnitId != -1 && SelectedUnit() == null)
            {
                SelectedUnitId = -1;
                Piloting = false;
            }
            if (SelectedUnitId == -1 && SelectableUnits().Count > 0) CycleSelection();
        }

        public void ThrottleUp() => SendThrottle(Throttle + ThrottleStep);
        public void ThrottleDown() => SendThrottle(Throttle - ThrottleStep);
        public void Stop() => SendThrottle(0);

        // While piloting, every press is sent, even an unchanged value (as main.js does).
        void SendThrottle(int next)
        {
            if (Piloting)
            {
                int wanted = ClampThrottle(next, 0);
                UnitView unit = SelectedUnit();
                if (unit == null) return;
                Throttle = wanted;
                _send(new Command { Type = "set_unit_helm", UnitId = unit.Id, Throttle = wanted, Rudder = Rudder, Climb = Climb });
                return;
            }
            int shipWanted = ClampThrottle(next, -25);
            if (shipWanted == Throttle || CarrierId < 0) return;
            Throttle = shipWanted;
            _send(new Command { Type = "set_throttle", CarrierId = CarrierId, Throttle = shipWanted });
        }

        public void SendRudder(int next)
        {
            if (Piloting)
            {
                UnitView unit = SelectedUnit();
                if (unit == null || next == Rudder) return;
                Rudder = next;
                _send(new Command { Type = "set_unit_helm", UnitId = unit.Id, Throttle = Throttle, Rudder = next, Climb = Climb });
                return;
            }
            if (next == Rudder || CarrierId < 0) return;
            Rudder = next;
            _send(new Command { Type = "set_rudder", CarrierId = CarrierId, Rudder = next });
        }

        public void SendClimb(int next)
        {
            if (!Piloting) return;
            UnitView unit = SelectedUnit();
            if (unit == null || next == Climb) return;
            Climb = next;
            _send(new Command { Type = "set_unit_helm", UnitId = unit.Id, Throttle = Throttle, Rudder = Rudder, Climb = next });
        }

        public void CycleSelection()
        {
            List<UnitView> units = SelectableUnits();
            if (units.Count == 0)
            {
                SelectedUnitId = -1;
                return;
            }
            int index = units.FindIndex(u => u.Id == SelectedUnitId);
            SelectedUnitId = units[(index + 1) % units.Count].Id;
        }

        public void Launch(int kind)
        {
            if (CarrierId < 0) return;
            _send(new Command { Type = "launch_unit", CarrierId = CarrierId, Kind = kind });
        }

        public void OrderEscort()
        {
            UnitView unit = SelectedUnit();
            if (unit == null) return;
            StopPiloting();
            _send(new Command { Type = "order_unit_escort", UnitId = unit.Id });
        }

        public void RecallSelected()
        {
            UnitView unit = SelectedUnit();
            if (unit == null) return;
            StopPiloting();
            _send(new Command { Type = "recall_unit", UnitId = unit.Id });
        }

        void StopPiloting()
        {
            if (!Piloting) return;
            UnitView unit = SelectedUnit();
            Piloting = false;
            if (unit != null) _send(new Command { Type = "release_control", UnitId = unit.Id });
            CarrierView carrier = OwnCarrierOf(_view);
            Throttle = carrier == null ? 0 : carrier.Throttle;
            Rudder = 0;
            Climb = 0;
        }

        public void TogglePiloting()
        {
            if (Piloting)
            {
                StopPiloting();
                return;
            }
            UnitView unit = SelectedUnit();
            if (unit == null) return;
            Piloting = true;
            Throttle = 100;
            Rudder = 0;
            Climb = 0;
            _send(new Command { Type = "take_control", UnitId = unit.Id });
        }
    }
}
