using System;

namespace Fastengine
{
    public readonly record struct Rect(float X, float Y, float Width, float Height);

    // The view and HUD arithmetic a native port of a browser game needs: the game renders at a fixed size and is
    // shown letterboxed in a window of any size, the mouse maps back to game pixels, Ctrl+wheel steps through the
    // browser's zoom levels, and CSS transitions animate HUD opacity the way the browser's do.
    public static class ViewMath
    {
        // The browser's zoom levels.
        public static readonly float[] Zooms = { 0.5f, 0.67f, 0.75f, 0.8f, 0.9f, 1, 1.1f, 1.25f, 1.5f, 1.75f, 2, 2.5f, 3 };

        // The largest width×height rectangle of the same shape centred in a screenW×screenH window.
        public static Rect Fit(float screenW, float screenH, int width, int height) => throw new NotImplementedException();

        // A window point (pixels) to the game's CSS pixels: undo the letterbox (view), scale to the outW×outH render,
        // then divide by the UI scale. Points in the bars map outside 0..outW/uiScale.
        public static (float X, float Y) ToOutput(float windowX, float windowY, Rect view, int outW, int outH, float uiScale)
            => throw new NotImplementedException();

        // The next zoom level above (step > 0) or below (step < 0) the current zoom, whatever level the current zoom
        // is at (a saved zoom may sit between levels; within 0.001 of a level counts as at that level); clamped to the
        // first and last level.
        public static float NextZoom(float zoom, int step) => throw new NotImplementedException();

        // CSS's "ease" timing function, cubic-bezier(0.25, 0.1, 0.25, 1): progress t in [0, 1] to output.
        public static float Ease(float t) => throw new NotImplementedException();
    }

    // "transition: opacity <duration>" between 0 (off) and 1 (on) with the default ease, as the browser runs it:
    // starts off; Set to the state it is already in changes nothing; turned around mid-way it runs from where it is,
    // over that share of the duration (CSS's reversing shortening factor), easing again from the start.
    public sealed class CssTransition
    {
        public CssTransition(double duration) => throw new NotImplementedException();

        public bool On { get; private set; }

        public void Set(bool on, double now) => throw new NotImplementedException();

        public float Value(double now) => throw new NotImplementedException();
    }
}
