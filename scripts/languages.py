"""Draw the "most used languages" card for the profile README.

Each public, non-fork repository counts equally: its language byte counts (from GitHub's
languages API, which ignores vendored files) are turned into shares, and the shares are
averaged across repositories. This stops one large notebook from swamping everything else.
Writes assets/languages-light.svg and assets/languages-dark.svg.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

USER = os.environ.get("GH_USER", "harsh-github007")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = Path(__file__).resolve().parents[1] / "assets"
COLORS = {  # GitHub's linguist colours
    "Python": "#3572A5", "JavaScript": "#f1e05a", "Jupyter Notebook": "#DA5B0B", "TeX": "#3D6117",
    "HTML": "#e34c26", "CSS": "#663399", "TypeScript": "#3178c6", "SQL": "#e38c00", "VBA": "#867db1",
    "Shell": "#89e051", "R": "#198CE7", "Java": "#b07219", "C++": "#f34b7d", "Other": "#8b949e",
}
TOP = 7


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def repos():
    names = sys.argv[1:]
    if names:
        return names
    out, page = [], 1
    while True:
        batch = get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner&page={page}")
        out += [r["name"] for r in batch if not r["fork"] and not r["archived"] and r["name"] != USER]
        if len(batch) < 100:
            return out
        page += 1


def shares():
    total, n = {}, 0
    for name in repos():
        langs = get(f"https://api.github.com/repos/{USER}/{name}/languages")
        size = sum(langs.values())
        if not size:
            continue
        n += 1
        for lang, b in langs.items():
            total[lang] = total.get(lang, 0) + b / size
    ranked = sorted(((v / n, k) for k, v in total.items()), reverse=True)
    top = [(k, v) for v, k in ranked[:TOP]]
    rest = sum(v for v, _ in ranked[TOP:])
    if rest > 0.005:
        top.append(("Other", rest))
    return top, n


def svg(top, n, dark):
    fg, muted, bg, border = ("#e6edf3", "#8b949e", "#0d1117", "#30363d") if dark else ("#1f2328", "#59636e", "#ffffff", "#d1d9e0")
    w, pad, bar_y = 460, 22, 64
    x, bar = pad, []
    for i, (lang, v) in enumerate(top):
        bw = (w - 2 * pad) * v
        bar.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{max(bw, 0.5):.1f}" height="10" fill="{COLORS.get(lang, COLORS["Other"])}"/>')
        x += bw
    rows = (len(top) + 1) // 2
    legend = []
    for i, (lang, v) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = pad + col * (w - 2 * pad) / 2, 100 + row * 24
        legend.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{COLORS.get(lang, COLORS["Other"])}"/>'
                      f'<text x="{lx + 16}" y="{ly}" class="t">{lang}</text>'
                      f'<text x="{lx + (w - 2 * pad) / 2 - 18}" y="{ly}" class="m" text-anchor="end">{100 * v:.1f}%</text>')
    h = 100 + rows * 24 + 8
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Most used languages">
<style>.h{{font:600 16px -apple-system,Segoe UI,Helvetica,Arial,sans-serif;fill:{fg}}}.s{{font:12px -apple-system,Segoe UI,Helvetica,Arial,sans-serif;fill:{muted}}}.t{{font:13px -apple-system,Segoe UI,Helvetica,Arial,sans-serif;fill:{fg}}}.m{{font:13px -apple-system,Segoe UI,Helvetica,Arial,sans-serif;fill:{muted}}}</style>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="8" fill="{bg}" stroke="{border}"/>
<text x="{pad}" y="32" class="h">Most used languages</text>
<text x="{pad}" y="50" class="s">Share of code, averaged across {n} repositories</text>
<clipPath id="c"><rect x="{pad}" y="{bar_y}" width="{w - 2 * pad}" height="10" rx="5"/></clipPath>
<g clip-path="url(#c)">{"".join(bar)}</g>
{"".join(legend)}
</svg>
'''


def commit(path, content):
    """Update a file through the contents API, so GitHub signs the commit."""
    import base64
    repo = os.environ["GITHUB_REPOSITORY"]
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        current = get(url)
        if base64.b64decode(current["content"]).decode() == content:
            return False
        sha = current["sha"]
    except urllib.error.HTTPError:
        sha = None
    body = {"message": f"Update {path}", "content": base64.b64encode(content.encode()).decode(), **({"sha": sha} if sha else {})}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT",
                                 headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {TOKEN}"})
    urllib.request.urlopen(req, timeout=30).read()
    return True


def main():
    top, n = shares()
    OUT.mkdir(exist_ok=True)
    for dark in (False, True):
        name = f"languages-{'dark' if dark else 'light'}.svg"
        content = svg(top, n, dark)
        (OUT / name).write_text(content)
        if os.environ.get("COMMIT") == "1":
            print(name, "updated" if commit(f"assets/{name}", content) else "unchanged")
    print(n, top)


if __name__ == "__main__":
    main()
