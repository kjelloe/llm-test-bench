using System.Collections.Generic;

namespace GameClient
{
    // The parts of a snapshot view the helm reads (CarrierDominion wire names in comments).
    public sealed class HelmView
    {
        public int Team;                                          // team
        public List<CarrierView> Carriers = new List<CarrierView>(); // carriers
        public List<UnitView> Units = new List<UnitView>();       // units
    }

    public sealed class CarrierView
    {
        public int Id, Team, Contact, Throttle, Rudder;            // id, team, contact, throttle, rudder
    }

    public sealed class UnitView
    {
        public int Id, Team, Kind, State;                          // id, team, kind, state
    }

    // A command to the server: Type plus the fields that message carries; the others stay null.
    // Wire form: { type, carrierId, unitId, throttle, rudder, climb, kind } with nulls left out.
    public sealed class Command
    {
        public string Type;
        public int? CarrierId, UnitId, Throttle, Rudder, Climb, Kind;
    }
}
