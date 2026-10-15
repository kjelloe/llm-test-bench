using System.Collections.Generic;
using GameClient;
using Xunit;

namespace GameClientTests
{
    // A test set that fails for every realistic single fault in Movement: systematic cases at each threshold the code
    // branches on (target cell vs current, flush position each way, assist offset exactly at +-AssistMin, blocked
    // assist lanes, the glide clamp, the speed cap on the assist step, negative coordinates for floor division,
    // both axes, x winning over y).
    public class MovementTests
    {
        const int C = 256, H = 128, S = Movement.SpeedBase;

        static Movement.Blocked Walls(params (int, int)[] cells)
        {
            var set = new HashSet<(int, int)>(cells);
            return (cx, cy) => set.Contains((cx, cy));
        }

        static (int, int) Step(int x, int y, int dx, int dy, Movement.Blocked b, int speed = S) => Movement.StepEntity(x, y, dx, dy, speed, b);

        [Fact] public void OpenRight() => Assert.Equal((3 * C + H + S, 2 * C + H), Step(3 * C + H, 2 * C + H, 1, 0, Walls()));
        [Fact] public void OpenUp() => Assert.Equal((3 * C + H, 2 * C + H - S), Step(3 * C + H, 2 * C + H, 0, -1, Walls()));
        [Fact] public void XWinsOverY() => Assert.Equal((3 * C + H + S, 2 * C + H), Step(3 * C + H, 2 * C + H, 1, 1, Walls()));
        [Fact] public void NoInput_NoMove() => Assert.Equal((3 * C + H, 2 * C + H), Step(3 * C + H, 2 * C + H, 0, 0, Walls((3, 2))));

        [Fact] public void FlushAgainstWall_Right() => Assert.Equal((4 * C - Movement.Body - 1, 2 * C + H), Step(3 * C + H, 2 * C + H, 1, 0, Walls((4, 2))));
        [Fact] public void FlushAgainstWall_Left() => Assert.Equal((3 * C + Movement.Body, 2 * C + H), Step(3 * C + H, 2 * C + H, -1, 0, Walls((2, 2))));
        [Fact] public void FlushAgainstWall_Down() => Assert.Equal((3 * C + H, 3 * C - Movement.Body - 1), Step(3 * C + H, 2 * C + H, 0, 1, Walls((3, 3))));

        // The lead looks speed + Body ahead: at this distance only the speed term reaches the wall cell.
        [Fact] public void LeadIncludesSpeed() => Assert.Equal((4 * C - Movement.Body - 1, 2 * C + H), Step(4 * C - Movement.Body - S + 1, 2 * C + H, 1, 0, Walls((4, 2))));

        // Standing in a blocked cell (on your own bomb) you can still walk within it.
        [Fact] public void BlockedOwnCell_CanMoveWithinIt() => Assert.Equal((3 * C + 20 + S, 2 * C + H), Step(3 * C + 20, 2 * C + H, 1, 0, Walls((3, 2))));

        [Fact] public void Glide_IsClampedToSpeed() => Assert.Equal((3 * C + H + S, 2 * C + H - 100 + S), Step(3 * C + H, 2 * C + H - 100, 1, 0, Walls()));
        [Fact] public void Glide_ReachesTheCentre() => Assert.Equal((3 * C + H + S, 2 * C + H), Step(3 * C + H, 2 * C + H - 20, 1, 0, Walls()));

        [Fact] public void AssistAtExactlyMin_SlidesDown() => Assert.Equal((4 * C - Movement.Body - 1, 2 * C + H + Movement.AssistMin + S),
            Step(3 * C + H, 2 * C + H + Movement.AssistMin, 1, 0, Walls((4, 2))));
        [Fact] public void AssistJustBelowMin_Stays() => Assert.Equal((4 * C - Movement.Body - 1, 2 * C + H + Movement.AssistMin - 1),
            Step(3 * C + H, 2 * C + H + Movement.AssistMin - 1, 1, 0, Walls((4, 2))));
        [Fact] public void AssistUp_AtExactlyMinusMin() => Assert.Equal((4 * C - Movement.Body - 1, 2 * C + H - Movement.AssistMin - S),
            Step(3 * C + H, 2 * C + H - Movement.AssistMin, 1, 0, Walls((4, 2))));
        [Fact] public void AssistDown_BlockedLane_Stays() => Assert.Equal((4 * C - Movement.Body - 1, 2 * C + H + 100),
            Step(3 * C + H, 2 * C + H + 100, 1, 0, Walls((4, 2), (4, 3))));
        [Fact] public void AssistUp_BlockedLane_Stays() => Assert.Equal((4 * C - Movement.Body - 1, 2 * C + H - 100),
            Step(3 * C + H, 2 * C + H - 100, 1, 0, Walls((4, 2), (4, 1))));
        [Fact] public void AssistStep_CappedBySpeed() => Assert.Equal((4 * C - Movement.Body - 1, 2 * C + H + 100 + S),
            Step(3 * C + H, 2 * C + H + 100, 1, 0, Walls((4, 2))));

        [Fact] public void WallAtNegativeCell_Left() => Assert.Equal((Movement.Body, H), Step(H, H, -1, 0, Walls((-1, 0))));
        [Fact] public void VerticalUsesColumnThenRow() => Assert.Equal((5 * C + H, 2 * C + Movement.Body), Step(5 * C + H, 2 * C + H, 0, -1, Walls((5, 1))));
    }
}
