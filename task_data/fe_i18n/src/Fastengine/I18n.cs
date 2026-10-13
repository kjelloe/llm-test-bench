using System;
using System.Collections.Generic;
using System.Globalization;

namespace Fastengine
{
    // fastengine spec D08: the game's text, as the browser client's client/i18n.js does it (js/i18n.js, the port's
    // reference): catalogues fetched from the server played on (never bundled), the language from -lang or else the
    // OS language, a missing key falls back to English and then to the key itself, {name} placeholders filled as the
    // browser fills them. A key missing from the language's catalogue is logged once ("[I18n] missing <lang> key
    // <key>"), however often it is asked for.
    public sealed class I18n
    {
        public const string DefaultLang = "en";
        public static readonly string[] Langs = { "en", "no" };

        readonly string _lang;
        readonly Dictionary<string, string> _catalog, _fallback;
        readonly Action<string> _log;

        public I18n(string lang, Dictionary<string, string> catalog, Dictionary<string, string> fallback, Action<string> log)
        {
            _lang = lang;
            _catalog = catalog;
            _fallback = fallback;
            _log = log;
        }

        // pickLang(requested, navigator.language): -lang wins when the game has it, else the OS language.
        public static string PickLang(string requested, string language)
        {
            if (requested != null && Array.IndexOf(Langs, requested) >= 0) return requested;
            var os = language ?? "";
            if (os is "nb" or "nn" or "no") os = "no";
            return Array.IndexOf(Langs, os) >= 0 ? os : DefaultLang;
        }

        // The OS language on Linux as navigator.language would give it: LC_ALL, then LC_MESSAGES, then LANG, skipping
        // unset or empty ones and the C/POSIX locales ("nb_NO.UTF-8" -> "nb_NO.UTF-8"; "" when there is none).
        public static string OsLanguage(Func<string, string> env)
        {
            var v = env("LANG");
            return string.IsNullOrEmpty(v) ? "" : v;
        }

        // The catalogue's URL on the server the socket belongs to: ws://host:port/path?query -> http://host:port/data/i18n/<lang>.json
        // (wss -> https, a default port left out).
        public static string CatalogUrl(string socketUrl, string lang)
        {
            var u = new UriBuilder(socketUrl) { Path = "/data/i18n/" + lang + ".json", Query = "" };
            return u.Uri.AbsoluteUri;
        }

        public string T(string key, params (string Name, object Value)[] vars)
        {
            var template = _catalog.TryGetValue(key, out var t) ? t : _fallback.TryGetValue(key, out var f) ? f : key;
            foreach (var (name, value) in vars) template = template.Replace("{" + name + "}", Convert.ToString(value, CultureInfo.InvariantCulture));
            return template;
        }
    }
}
