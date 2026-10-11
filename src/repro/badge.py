"""SVG badges: 'reproduced by N independent parties'."""

import xml.sax.saxutils as sax


def badge_svg(recipe_name, parties, self_attested=0, attestations=0):
    label = "reproduced by"
    if parties == 0 and self_attested > 0:
        value, color = f"author-verified", "#9e6a03"
    elif parties == 0:
        value, color = "not yet reproduced", "#6b7280"
    else:
        value = f"{parties} independent {'party' if parties == 1 else 'parties'}"
        if self_attested:
            value += f" (+{self_attested} author)"
        color = "#1f883d" if parties >= 3 else "#0969da"
    label_w = 118
    value_w = max(90, 7 * len(value) + 18)
    w = label_w + value_w
    l = sax.escape(label)
    v = sax.escape(value)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{l}: {v}">
  <title>{l}: {v} — {sax.escape(recipe_name)} on reproledger</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <rect rx="3" width="{w}" height="20" fill="#555"/>
  <rect rx="3" x="{label_w}" width="{value_w}" height="20" fill="{color}"/>
  <rect rx="3" width="{w}" height="20" fill="url(#s)"/>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">
    <text x="{label_w/2}" y="15">{l}</text>
    <text x="{label_w + value_w/2}" y="15">{v}</text>
  </g>
</svg>
"""
