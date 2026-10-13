using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace Fastengine.Net
{
    // From fastengine's Net/SocketUrl.cs and Net/UpdateNotice.cs.
    public static class SocketUrl
    {
        public static string With(string url, string key, string value)
        {
            var builder = new UriBuilder(url);
            var kept = new List<string>();
            foreach (var part in builder.Query.TrimStart('?').Split('&'))
                if (part != "" && part.Split('=')[0] != key) kept.Add(part);
            if (!string.IsNullOrEmpty(value)) kept.Add(key + "=" + Uri.EscapeDataString(value));
            builder.Query = string.Join("&", kept);
            return builder.Uri.AbsoluteUri;
        }
    }

    public static class UpdateNotice
    {
        static readonly Regex ProtocolRefusal = new(@"^protocol \d+ required\b");

        public static string PageFor(string reason, string socketUrl)
        {
            if (reason == null || !ProtocolRefusal.IsMatch(reason)) return null;
            var u = new Uri(socketUrl);
            return $"{(u.Scheme == "wss" ? "https" : "http")}://{u.Authority}/native";
        }

        public static string For(string reason, string socketUrl)
        {
            var page = PageFor(reason, socketUrl);
            if (page == null) return null;
            Log.Line($"[Net] update needed {page}");
            return $"A newer version is out: {page}";
        }
    }
}
