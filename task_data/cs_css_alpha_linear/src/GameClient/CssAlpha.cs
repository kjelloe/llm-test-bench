using UnityEngine;

namespace GameClient
{
    // HUD panels from the browser game are drawn with the CSS colour and alpha copied straight into a material.
    // The project uses Linear colour space, and the panels come out lighter than in the browser (incident F11).
    public static class CssAlpha
    {
        // What the browser draws: CSS rgba(css, alpha) over an opaque backdrop. Assumed to blend like Unity does.
        public static Color32 BrowserOver(Color32 backdrop, Color32 css, float alpha) => LinearOver(backdrop, css, alpha);

        // What a Linear-colour-space Unity project draws for a material of colour src and this alpha.
        public static Color32 LinearOver(Color32 backdrop, Color32 src, float alpha)
        {
            Color b = ToColor(backdrop), s = ToColor(src);
            Color lin = Color.Lerp(new Color(Mathf.Pow(b.r, 2.2f), Mathf.Pow(b.g, 2.2f), Mathf.Pow(b.b, 2.2f)),
                new Color(Mathf.Pow(s.r, 2.2f), Mathf.Pow(s.g, 2.2f), Mathf.Pow(s.b, 2.2f)), alpha);
            return new Color32((byte)(Mathf.Pow(lin.r, 1 / 2.2f) * 255), (byte)(Mathf.Pow(lin.g, 1 / 2.2f) * 255),
                (byte)(Mathf.Pow(lin.b, 1 / 2.2f) * 255), 255);
        }

        // The alpha to give the Unity material so it draws what the browser draws over this backdrop.
        public static float AlphaForLinear(Color32 css, float cssAlpha, Color32 backdrop) => cssAlpha;

        static Color ToColor(Color32 c) => new Color(c.r / 255f, c.g / 255f, c.b / 255f, 1f);
    }
}
