using System;
using System.Collections.Generic;

namespace Fastengine
{
    public enum Justify { FlexStart, Center, SpaceBetween, FlexEnd }
    public enum Align { FlexStart, Center, FlexEnd }
    public readonly record struct Box(float Width, float Height);

    public static class FlexLayout
    {
        public static (float X, float Y)[] WrapRow(float containerWidth, float rowGap, float columnGap,
            Justify justify, Align align, IReadOnlyList<Box> items)
        {
            var result = new (float X, float Y)[items.Count];
            // Break into lines: an item joins the line if the line's items, their column gaps and it fit.
            var lines = new List<(int start, int end)>();
            int first = 0;
            float used = 0;
            for (int i = 0; i < items.Count; i++)
            {
                float need = i == first ? items[i].Width : used + columnGap + items[i].Width;
                if (i > first && need > containerWidth)
                {
                    lines.Add((first, i));
                    first = i;
                    used = items[i].Width;
                }
                else used = need;
            }
            if (items.Count > 0) lines.Add((first, items.Count));

            float y = 0;
            foreach (var (start, end) in lines)
            {
                int n = end - start;
                float width = 0, height = 0;
                for (int i = start; i < end; i++) { width += items[i].Width; height = Math.Max(height, items[i].Height); }
                float free = containerWidth - width - columnGap * (n - 1);
                float x = 0, between = columnGap;
                switch (justify)
                {
                    case Justify.Center: x = free / 2; break;
                    case Justify.FlexEnd: x = free; break;
                    case Justify.SpaceBetween when n > 1 && free > 0: between = columnGap + free / (n - 1); break;
                }
                for (int i = start; i < end; i++)
                {
                    float dy = align switch
                    {
                        Align.Center => (height - items[i].Height) / 2,
                        Align.FlexEnd => height - items[i].Height,
                        _ => 0,
                    };
                    result[i] = (x, y + dy);
                    x += items[i].Width + between;
                }
                y += height + rowGap;
            }
            return result;
        }
    }
}
