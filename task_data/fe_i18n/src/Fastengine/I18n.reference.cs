using System;
using System.Collections.Generic;
using System.Globalization;

namespace Fastengine
{
    public sealed class I18n
    {
        public const string DefaultLang = "en";
        public static readonly string[] Langs = { "en", "no" };

        readonly string _lang;
        readonly Dictionary<string, string> _catalog, _fallback;
        readonly Action<string> _log;
        readonly HashSet<string> _logged = new();

        public I18n(string lang, Dictionary<string, string> catalog, Dictionary<string, string> fallback, Action<string> log)
        {
            _lang = lang;
            _catalog = catalog;
            _fallback = fallback;
            _log = log;
        }

        public static string PickLang(string requested, string language)
        {
            if (requested != null && Array.IndexOf(Langs, requested) >= 0) return requested;
            var browser = language ?? "";
            browser = browser[..Math.Min(2, browser.Length)].ToLowerInvariant();
            if (browser is "nb" or "nn" or "no") return "no";
            return Array.IndexOf(Langs, browser) >= 0 ? browser : DefaultLang;
        }

        public static string OsLanguage(Func<string, string> env)
        {
            foreach (var name in new[] { "LC_ALL", "LC_MESSAGES", "LANG" })
            {
                var v = env(name);
                if (!string.IsNullOrEmpty(v) && v != "C" && v != "POSIX") return v;
            }
            return "";
        }

        public static string CatalogUrl(string socketUrl, string lang)
        {
            var u = new UriBuilder(socketUrl) { Path = "/data/i18n/" + lang + ".json", Query = "" };
            u.Scheme = u.Scheme == "wss" ? "https" : "http";
            if (u.Uri.IsDefaultPort) u.Port = -1;
            return u.Uri.AbsoluteUri;
        }

        public string T(string key, params (string Name, object Value)[] vars)
        {
            if (!_catalog.TryGetValue(key, out var template))
            {
                if (_logged.Add(key)) _log?.Invoke($"[I18n] missing {_lang} key {key}");
                if (!_fallback.TryGetValue(key, out template)) template = key;
            }
            foreach (var (name, value) in vars) template = template.Replace("{" + name + "}", JsString(value));
            return template;
        }

        // JavaScript's String(value) for the values a HUD passes: numbers as JS prints them, true/false, null.
        static string JsString(object value) => value switch
        {
            null => "null",
            bool b => b ? "true" : "false",
            string s => s,
            double d => JsNumber(d),
            float f => JsNumber(f),
            int or long or short or byte => Convert.ToString(value, CultureInfo.InvariantCulture),
            _ => Convert.ToString(value, CultureInfo.InvariantCulture),
        };

        // ECMAScript Number::toString: the shortest round-trip digits, placed by the spec's rules.
        static string JsNumber(double d)
        {
            if (double.IsNaN(d)) return "NaN";
            if (double.IsInfinity(d)) return d > 0 ? "Infinity" : "-Infinity";
            if (d == 0) return "0";
            var r = d.ToString("R", CultureInfo.InvariantCulture);
            var sign = r[0] == '-' ? "-" : "";
            if (sign.Length > 0) r = r[1..];
            int e = r.IndexOf('E'), exp = 0;
            var mantissa = r;
            if (e >= 0) { mantissa = r[..e]; exp = int.Parse(r[(e + 1)..], CultureInfo.InvariantCulture); }
            int dot = mantissa.IndexOf('.');
            var digits = mantissa.Replace(".", "");
            int n = (dot < 0 ? mantissa.Length : dot) + exp;
            int lead = digits.Length - digits.TrimStart('0').Length;
            digits = digits.TrimStart('0').TrimEnd('0');
            n -= lead;
            int k = digits.Length;
            string body;
            if (k <= n && n <= 21) body = digits + new string('0', n - k);
            else if (0 < n && n <= 21) body = digits[..n] + "." + digits[n..];
            else if (-6 < n && n <= 0) body = "0." + new string('0', -n) + digits;
            else
            {
                int x = n - 1;
                body = (k == 1 ? digits : digits[0] + "." + digits[1..]) + "e" + (x >= 0 ? "+" : "-") + Math.Abs(x).ToString(CultureInfo.InvariantCulture);
            }
            return sign + body;
        }
    }
}
