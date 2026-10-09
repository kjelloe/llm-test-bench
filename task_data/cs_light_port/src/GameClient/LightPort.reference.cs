using UnityEngine;

namespace GameClient
{
    // Lighting values for the Unity (URP, Linear colour space) ports of the browser clients, whose
    // three.js r162 light setups are in js/lights.js. Unity's API takes every Color (light.color,
    // RenderSettings.ambientLight/ambientSkyColor/...) in sRGB (gamma) space and linearises it
    // itself in a Linear project.
    public static class LightPort
    {
        // A 0xRRGGBB hex colour as a Unity Color.
        public static Color FromHex(uint rgb) =>
            new Color(((rgb >> 16) & 0xff) / 255f, ((rgb >> 8) & 0xff) / 255f, (rgb & 0xff) / 255f, 1f);

        // three.js r155+ lights are physical: its Lambert BRDF divides by PI and Unity's does not.
        public static float Intensity(float threeIntensity) => threeIntensity / Mathf.PI;

        // three.js scales the colour in linear space; Unity wants the result back in sRGB.
        public static Color AmbientFlat(uint rgb, float intensity) => (FromHex(rgb).linear * Intensity(intensity)).gamma;

        // The hemisphere blends sky and ground by the normal, in linear space: a horizontal normal
        // gets their average.
        public static (Color sky, Color equator, Color ground) AmbientTrilight(uint sky, uint ground, float intensity)
        {
            Color s = FromHex(sky).linear * Intensity(intensity), g = FromHex(ground).linear * Intensity(intensity);
            return (s.gamma, ((s + g) / 2).gamma, g.gamma);
        }

        // Unity's directional light shines along its forward axis; z is mirrored into Unity's axes.
        public static Quaternion DirectionalRotation(Vector3 threePosition, Vector3 threeTarget)
        {
            Vector3 d = threeTarget - threePosition;
            return Quaternion.LookRotation(new Vector3(d.x, d.y, -d.z));
        }
    }
}
