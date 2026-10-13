using System;
using System.Collections.Generic;

namespace Fastengine
{
    public enum Justify { FlexStart, Center, SpaceBetween, FlexEnd }
    public enum Align { FlexStart, Center, FlexEnd }
    public readonly record struct Box(float Width, float Height);

    // The HUD's port of a CSS row that wraps:
    //   display: flex; flex-direction: row; flex-wrap: wrap; row-gap; column-gap; justify-content; align-items
    // with items that neither grow nor shrink (flex: none). Returns each item's top-left offset from the
    // container, as the browser lays it out. This first version came from the top bar, which had no gap set.
    public static class FlexLayout
    {
        public static (float X, float Y)[] WrapRow(float containerWidth, float rowGap, float columnGap,
            Justify justify, Align align, IReadOnlyList<Box> items)
        {
            var result = new (float X, float Y)[items.Count];
            float x = 0, y = 0, lineHeight = 0;
            for (int i = 0; i < items.Count; i++)
            {
                if (x > 0 && x + items[i].Width > containerWidth)
                {
                    x = 0;
                    y += lineHeight;
                    lineHeight = 0;
                }
                result[i] = (x, y);
                x += items[i].Width + columnGap;
                lineHeight = Math.Max(lineHeight, items[i].Height);
            }
            return result;
        }
    }
}
