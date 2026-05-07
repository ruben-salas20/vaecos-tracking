"""SVG chart generators — ported verbatim from v0.3/vaecos_v03/render.py."""
from __future__ import annotations
from html import escape


def line_chart(
    title: str,
    points: list[tuple[str, float]],
    width: int = 640,
    height: int = 200,
    color: str = "#dc2626",
) -> str:
    """SVG line chart. points is a list of (label, value); x-axis is discrete by index."""
    if not points:
        return (
            '<div class="chart-wrap"><div class="chart-title">'
            f'{escape(title)}</div>'
            '<p class="muted" style="padding:20px 4px">Sin datos en el periodo.</p></div>'
        )

    margin_x, margin_top, margin_bottom = 36, 12, 28
    plot_w = width - margin_x * 2
    plot_h = height - margin_top - margin_bottom
    values = [p[1] for p in points]
    max_v = max(values) or 1
    n = len(points)

    def x_for(i: int) -> float:
        if n == 1:
            return margin_x + plot_w / 2
        return margin_x + (plot_w * i / (n - 1))

    def y_for(v: float) -> float:
        return margin_top + plot_h - (plot_h * v / max_v)

    coords = " ".join(f"{x_for(i):.1f},{y_for(v):.1f}" for i, v in enumerate(values))
    dots = "".join(
        f'<circle cx="{x_for(i):.1f}" cy="{y_for(v):.1f}" r="3" fill="{color}">'
        f'<title>{escape(points[i][0])}: {v:g}</title></circle>'
        for i, v in enumerate(values)
    )
    grid_y = []
    for step in (0.25, 0.5, 0.75, 1.0):
        gy = margin_top + plot_h - plot_h * step
        grid_y.append(
            f'<line x1="{margin_x}" y1="{gy:.1f}" x2="{margin_x + plot_w}" y2="{gy:.1f}" '
            f'stroke="#e2e8f0" stroke-width="1" stroke-dasharray="2 3"/>'
        )
        label_v = max_v * step
        grid_y.append(
            f'<text x="{margin_x - 6}" y="{gy + 3:.1f}" font-size="9" fill="#94a3b8" '
            f'text-anchor="end">{label_v:g}</text>'
        )
    x_ticks = []
    tick_every = max(1, n // 8)
    for i, (label, _) in enumerate(points):
        if i % tick_every != 0 and i != n - 1:
            continue
        short = label[5:] if len(label) >= 10 else label
        x_ticks.append(
            f'<text x="{x_for(i):.1f}" y="{height - 8}" font-size="9" fill="#64748b" '
            f'text-anchor="middle">{escape(short)}</text>'
        )

    return (
        '<div class="chart-wrap">'
        f'<div class="chart-title">{escape(title)}</div>'
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        'preserveAspectRatio="xMidYMid meet" role="img">'
        + "".join(grid_y)
        + f'<polyline fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linejoin="round" points="{coords}"/>'
        + dots
        + "".join(x_ticks)
        + "</svg></div>"
    )


def stacked_bar_chart(
    title: str,
    days: list[str],
    series: list[tuple[str, list[int], str]],
    width: int = 640,
    height: int = 220,
) -> str:
    """SVG stacked bar chart. series is [(label, values_per_day, color)]."""
    if not days or not series:
        return (
            '<div class="chart-wrap"><div class="chart-title">'
            f'{escape(title)}</div>'
            '<p class="muted" style="padding:20px 4px">Sin datos en el periodo.</p></div>'
        )

    margin_x, margin_top, margin_bottom = 36, 12, 48
    plot_w = width - margin_x * 2
    plot_h = height - margin_top - margin_bottom
    n = len(days)
    totals = [sum(s[1][i] for s in series) for i in range(n)]
    max_total = max(totals) or 1
    bar_w = max(4, plot_w / max(n, 1) * 0.7)
    gap = plot_w / max(n, 1) - bar_w

    grid_y = []
    for step in (0.25, 0.5, 0.75, 1.0):
        gy = margin_top + plot_h - plot_h * step
        grid_y.append(
            f'<line x1="{margin_x}" y1="{gy:.1f}" x2="{margin_x + plot_w}" y2="{gy:.1f}" '
            f'stroke="#e2e8f0" stroke-width="1" stroke-dasharray="2 3"/>'
        )
        label_v = max_total * step
        grid_y.append(
            f'<text x="{margin_x - 6}" y="{gy + 3:.1f}" font-size="9" fill="#94a3b8" '
            f'text-anchor="end">{label_v:g}</text>'
        )

    bars = []
    for i, day in enumerate(days):
        x = margin_x + i * (bar_w + gap) + gap / 2
        cursor_y = margin_top + plot_h
        for label, values, color in series:
            v = values[i]
            if v <= 0:
                continue
            h_px = plot_h * v / max_total
            cursor_y -= h_px
            bars.append(
                f'<rect x="{x:.1f}" y="{cursor_y:.1f}" width="{bar_w:.1f}" '
                f'height="{h_px:.1f}" fill="{color}">'
                f'<title>{escape(day)} — {escape(label)}: {v}</title></rect>'
            )

    x_ticks = []
    tick_every = max(1, n // 10)
    for i, day in enumerate(days):
        if i % tick_every != 0 and i != n - 1:
            continue
        short = day[5:] if len(day) >= 10 else day
        x_center = margin_x + i * (bar_w + gap) + gap / 2 + bar_w / 2
        x_ticks.append(
            f'<text x="{x_center:.1f}" y="{height - 30}" font-size="9" fill="#64748b" '
            f'text-anchor="middle">{escape(short)}</text>'
        )

    legend_items = []
    lx = margin_x
    for label, _values, color in series:
        legend_items.append(
            f'<rect x="{lx}" y="{height - 16}" width="10" height="10" fill="{color}" rx="2"/>'
            f'<text x="{lx + 14}" y="{height - 7}" font-size="10" fill="#475569">'
            f'{escape(label)}</text>'
        )
        lx += 14 + len(label) * 6 + 14

    return (
        '<div class="chart-wrap">'
        f'<div class="chart-title">{escape(title)}</div>'
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        'preserveAspectRatio="xMidYMid meet" role="img">'
        + "".join(grid_y)
        + "".join(bars)
        + "".join(x_ticks)
        + "".join(legend_items)
        + "</svg></div>"
    )
