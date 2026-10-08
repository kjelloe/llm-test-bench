using System;
using GameClient;
using Xunit;

namespace GameClientTests
{
    public class SnapCodecTests
    {
        // Captured from the Node server (protocol v3).
        const string HelloV3 =
            "{\"t\":\"hello\",\"v\":3,\"id\":7,\"cfg\":{\"tickHz\":20,\"cell\":256}," +
            "\"roster\":[{\"id\":7,\"name\":\"ALPHA\",\"color\":16711680,\"bot\":0}," +
            "{\"id\":9,\"name\":\"BOT-2\",\"color\":65280,\"bot\":1}]}";

        const string Snap =
            "{\"t\":\"snap\",\"tick\":1042,\"phase\":\"play\",\"left\":3,\"round\":2," +
            "\"p\":[[7,\"a\",1408,896,1,0,55,2,3,48,1,0,4,1,0]," +
            "[9,\"d\",3200,640,0,-1,0,1,2,40,0,12,0,0,1]," +
            "[12,\"w\",0,0,0,0,0,1,1,32,1,0,0,0,0]]," +
            "\"b\":[[3,1408,1152,37,3,1]]," +
            "\"f\":[[5,4]],\"d\":[],\"ev\":[{\"k\":\"bomb\",\"id\":3}]}";

        static ProtocolException Rejects(SnapCodec codec, string json) =>
            Assert.Throws<ProtocolException>(() => codec.Decode(json));

        [Fact]
        public void Hello_V3_PopulatesRoster()
        {
            var codec = new SnapCodec();
            var hello = Assert.IsType<HelloMessage>(codec.Decode(HelloV3));
            Assert.Equal(3, hello.Version);
            Assert.Equal(7, hello.PlayerId);
            Assert.Equal(2, hello.Roster.Count);
            Assert.Equal(2, codec.Roster.Entries.Count);
            RosterEntry bot = codec.Roster.Entries[9];
            Assert.Equal("BOT-2", bot.Name);
            Assert.Equal(65280, bot.Color);
            Assert.True(bot.Bot);
            Assert.False(codec.Roster.Entries[7].Bot);
        }

        [Fact]
        public void Hello_V2_HasNoColorAndDefaultsToZero()
        {
            var codec = new SnapCodec();
            var hello = Assert.IsType<HelloMessage>(codec.Decode(
                "{\"t\":\"hello\",\"v\":2,\"id\":1,\"roster\":[{\"id\":1,\"name\":\"OLD\",\"bot\":0}]}"));
            Assert.Equal(2, hello.Version);
            Assert.Equal(0, codec.Roster.Entries[1].Color);
            Assert.Equal("OLD", codec.Roster.Entries[1].Name);
        }

        [Fact]
        public void Hello_V3_RequiresColor()
        {
            var codec = new SnapCodec();
            Assert.Equal(RejectReason.BadField, Rejects(codec,
                "{\"t\":\"hello\",\"v\":3,\"id\":1,\"roster\":[{\"id\":1,\"name\":\"X\",\"bot\":0}]}").Reason);
        }

        [Theory]
        [InlineData(1)]
        [InlineData(4)]
        [InlineData(0)]
        public void Hello_UnsupportedVersion_IsVersionMismatch(int v)
        {
            var codec = new SnapCodec();
            // Unsupported versions are rejected before the rest of the message is validated.
            Assert.Equal(RejectReason.VersionMismatch,
                Rejects(codec, "{\"t\":\"hello\",\"v\":" + v + ",\"whatever\":true}").Reason);
        }

        [Fact]
        public void Hello_MissingVersion_IsBadField()
        {
            var codec = new SnapCodec();
            Assert.Equal(RejectReason.BadField, Rejects(codec, "{\"t\":\"hello\",\"id\":1,\"roster\":[]}").Reason);
            Assert.Equal(RejectReason.BadField, Rejects(codec, "{\"t\":\"hello\",\"v\":\"3\",\"id\":1,\"roster\":[]}").Reason);
        }

        [Fact]
        public void Hello_ReplacesPreviousRoster()
        {
            var codec = new SnapCodec();
            codec.Decode(HelloV3);
            codec.Decode("{\"t\":\"hello\",\"v\":3,\"id\":4,\"roster\":[{\"id\":4,\"name\":\"NEW\",\"color\":1,\"bot\":0}]}");
            Assert.Single(codec.Roster.Entries);
            Assert.Equal("NEW", codec.Roster.Entries[4].Name);
        }

        [Fact]
        public void Snap_DecodesPositionalRows_AndMergesIdentity()
        {
            var codec = new SnapCodec();
            codec.Decode(HelloV3);
            var snap = Assert.IsType<SnapMessage>(codec.Decode(Snap));
            Assert.Equal(1042, snap.Tick);
            Assert.Equal("play", snap.Phase);
            Assert.Equal(3, snap.Players.Count);

            PlayerState a = snap.Players[0];
            Assert.Equal(7, a.Id);
            Assert.Equal(PlayerStatus.Alive, a.Status);
            Assert.Equal(1408, a.X);
            Assert.Equal(896, a.Y);
            Assert.Equal(1, a.Dx);
            Assert.Equal(0, a.Dy);
            Assert.Equal(55, a.Seq);
            Assert.Equal(2, a.Cap);
            Assert.Equal(3, a.Blast);
            Assert.Equal(48, a.Speed);
            Assert.Equal(1, a.Remaining);
            Assert.Equal(0, a.Invulnerable);
            Assert.Equal(4, a.Kills);
            Assert.Equal(1, a.Wins);
            Assert.Equal(0, a.Afk);
            Assert.Equal("ALPHA", a.Name);
            Assert.Equal(16711680, a.Color);
            Assert.False(a.Bot);

            PlayerState d = snap.Players[1];
            Assert.Equal(PlayerStatus.Dead, d.Status);
            Assert.Equal(-1, d.Dy);
            Assert.Equal(12, d.Invulnerable);
            Assert.Equal(1, d.Afk);
            Assert.True(d.Bot);

            Assert.Equal(PlayerStatus.Waiting, snap.Players[2].Status);

            BombState bomb = Assert.Single(snap.Bombs);
            Assert.Equal(3, bomb.Id);
            Assert.Equal(1408, bomb.X);
            Assert.Equal(1152, bomb.Y);
            Assert.Equal(37, bomb.Fuse);
            Assert.Equal(3, bomb.Blast);
            Assert.Equal(1, bomb.Remaining);
        }

        [Fact]
        public void Snap_UnknownPlayer_GetsPlaceholderIdentity()
        {
            var codec = new SnapCodec();
            codec.Decode(HelloV3);
            var snap = (SnapMessage)codec.Decode(Snap);
            PlayerState unknown = snap.Players[2];
            Assert.Equal(12, unknown.Id);
            Assert.Equal("?", unknown.Name);
            Assert.Equal(0, unknown.Color);
            Assert.False(unknown.Bot);
        }

        [Fact]
        public void Snap_UnknownStatusCode_IsWaiting()
        {
            var codec = new SnapCodec();
            var snap = (SnapMessage)codec.Decode(
                "{\"t\":\"snap\",\"tick\":1,\"phase\":\"lobby\",\"p\":[[1,\"z\",0,0,0,0,0,0,0,0,0,0,0,0,0]],\"b\":[]}");
            Assert.Equal(PlayerStatus.Waiting, snap.Players[0].Status);
        }

        [Fact]
        public void Snap_ExtraTrailingValuesAndUnknownFields_AreIgnored()
        {
            // A newer server appends fields to rows and adds top-level keys; older clients must cope.
            var codec = new SnapCodec();
            var snap = (SnapMessage)codec.Decode(
                "{\"t\":\"snap\",\"tick\":5,\"phase\":\"play\",\"future\":{\"x\":1}," +
                "\"p\":[[1,\"a\",256,512,0,0,3,1,1,32,1,0,0,0,0,99,\"new\"]],\"b\":[[2,0,0,10,1,1,7]]}");
            Assert.Equal(256, snap.Players[0].X);
            Assert.Equal(0, snap.Players[0].Afk);
            Assert.Equal(10, snap.Bombs[0].Fuse);
        }

        [Fact]
        public void Snap_ShortRow_IsBadField()
        {
            var codec = new SnapCodec();
            Assert.Equal(RejectReason.BadField, Rejects(codec,
                "{\"t\":\"snap\",\"tick\":1,\"phase\":\"play\",\"p\":[[1,\"a\",0,0,0,0,0,0,0,0,0,0,0,0]],\"b\":[]}").Reason);
            Assert.Equal(RejectReason.BadField, Rejects(codec,
                "{\"t\":\"snap\",\"tick\":1,\"phase\":\"play\",\"p\":[],\"b\":[[1,2,3]]}").Reason);
        }

        [Theory]
        [InlineData("1.5")]
        [InlineData("3000000000")]
        [InlineData("\"5\"")]
        [InlineData("null")]
        [InlineData("true")]
        public void Snap_NonInt32Values_AreBadField(string x)
        {
            var codec = new SnapCodec();
            Assert.Equal(RejectReason.BadField, Rejects(codec,
                "{\"t\":\"snap\",\"tick\":1,\"phase\":\"play\",\"p\":[[1,\"a\"," + x + ",0,0,0,0,0,0,0,0,0,0,0,0]],\"b\":[]}").Reason);
        }

        [Fact]
        public void Snap_MissingRequiredFields_AreBadField()
        {
            var codec = new SnapCodec();
            Assert.Equal(RejectReason.BadField, Rejects(codec, "{\"t\":\"snap\",\"tick\":1,\"phase\":\"play\",\"p\":[]}").Reason);
            Assert.Equal(RejectReason.BadField, Rejects(codec, "{\"t\":\"snap\",\"phase\":\"play\",\"p\":[],\"b\":[]}").Reason);
            Assert.Equal(RejectReason.BadField, Rejects(codec, "{\"t\":\"snap\",\"tick\":1,\"phase\":7,\"p\":[],\"b\":[]}").Reason);
        }

        [Fact]
        public void Reject_IsDecoded()
        {
            var msg = Assert.IsType<RejectMessage>(new SnapCodec().Decode("{\"t\":\"reject\",\"reason\":\"full\",\"extra\":1}"));
            Assert.Equal("full", msg.Reason);
        }

        [Theory]
        [InlineData("{not json", RejectReason.BadJson)]
        [InlineData("", RejectReason.BadJson)]
        [InlineData("[1,2]", RejectReason.BadShape)]
        [InlineData("\"snap\"", RejectReason.BadShape)]
        [InlineData("{\"x\":1}", RejectReason.BadShape)]
        [InlineData("{\"t\":5}", RejectReason.BadShape)]
        [InlineData("{\"t\":\"teleport\"}", RejectReason.UnknownType)]
        public void MalformedMessages_AreClassified(string json, RejectReason expected)
        {
            Assert.Equal(expected, Rejects(new SnapCodec(), json).Reason);
        }

        [Fact]
        public void EncodeInput_MatchesServerFormatExactly()
        {
            var codec = new SnapCodec();
            Assert.Equal("{\"t\":\"in\",\"seq\":5,\"dx\":1,\"dy\":0}", codec.EncodeInput(5, 1, 0, false));
            Assert.Equal("{\"t\":\"in\",\"seq\":6,\"dx\":0,\"dy\":-1,\"b\":1}", codec.EncodeInput(6, 0, -1, true));
            Assert.Equal("{\"t\":\"in\",\"seq\":0,\"dx\":0,\"dy\":0}", codec.EncodeInput(0, 0, 0, false));
        }

        [Fact]
        public void EncodeInput_RejectsInvalidInput()
        {
            var codec = new SnapCodec();
            Assert.ThrowsAny<ArgumentException>(() => codec.EncodeInput(1, 1, 1, false));
            Assert.ThrowsAny<ArgumentException>(() => codec.EncodeInput(1, 2, 0, false));
            Assert.ThrowsAny<ArgumentException>(() => codec.EncodeInput(1, 0, -2, false));
            Assert.ThrowsAny<ArgumentException>(() => codec.EncodeInput(-1, 0, 0, false));
        }
    }
}
