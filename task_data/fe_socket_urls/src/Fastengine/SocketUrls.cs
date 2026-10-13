using System;

namespace Fastengine.Net
{
    public static class SocketUrl
    {
        // The URL with one query parameter set (any existing one with that exact key removed, the new one added
        // last, the other parameters kept in their order), or removed when value is null or empty. The value is
        // percent-escaped as a URI data string.
        public static string With(string url, string key, string value) => throw new NotImplementedException();
    }

    // A refusal at the door for another protocol means this build is out of date. The game servers word it
    // "protocol <n> required, client has <m>" (the reason starts with that) and serve their native downloads at
    // /native on the same origin as the socket: ws becomes http, wss becomes https, host and port kept (a default
    // port is not written), path, query and fragment dropped.
    public static class UpdateNotice
    {
        // The download page when the reason is the protocol; null for any other refusal (or none).
        public static string PageFor(string reason, string socketUrl) => throw new NotImplementedException();

        // The line to show the player, "A newer version is out: <page>", logged as "[Net] update needed <page>";
        // null (and nothing logged) for any other refusal.
        public static string For(string reason, string socketUrl) => throw new NotImplementedException();
    }
}
