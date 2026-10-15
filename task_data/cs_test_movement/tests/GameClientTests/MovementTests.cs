using GameClient;
using Xunit;

namespace GameClientTests
{
    // Tests for Movement.StepEntity (src/GameClient/Movement.cs, a port of js/movement.mjs that the server runs
    // verbatim). This first test passed the first time it ran.
    public class MovementTests
    {
        static bool Open(int cx, int cy) => false;

        [Fact]
        public void MovesRightInTheOpen()
        {
            var (x, y) = Movement.StepEntity(3 * 256 + 128, 2 * 256 + 128, 1, 0, Movement.SpeedBase, Open);
            Assert.Equal(3 * 256 + 128 + Movement.SpeedBase, x);
            Assert.Equal(2 * 256 + 128, y);
        }
    }
}
