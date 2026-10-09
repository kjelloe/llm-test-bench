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

        // Light.intensity for a three.js DirectionalLight of this intensity.
        public static float Intensity(float threeIntensity) => threeIntensity;

        // RenderSettings.ambientLight (AmbientMode.Flat) for THREE.AmbientLight(rgb, intensity).
        public static Color AmbientFlat(uint rgb, float intensity) => FromHex(rgb) * intensity;

        // RenderSettings.ambientSkyColor / ambientEquatorColor / ambientGroundColor (AmbientMode.Trilight)
        // for THREE.HemisphereLight(sky, ground, intensity).
        public static (Color sky, Color equator, Color ground) AmbientTrilight(uint sky, uint ground, float intensity)
        {
            Color s = FromHex(sky) * intensity, g = FromHex(ground) * intensity;
            return (s, Color.Lerp(s, g, 0.5f), g);
        }

        // Transform.rotation for a directional light at threePosition aimed at threeTarget (three.js
        // world coordinates; the Unity scene maps three's (x, y, z) to (x, y, -z)).
        public static Quaternion DirectionalRotation(Vector3 threePosition, Vector3 threeTarget) =>
            Quaternion.LookRotation(threeTarget - threePosition);
    }
}
