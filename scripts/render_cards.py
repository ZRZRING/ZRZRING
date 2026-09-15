#!/usr/bin/env python3
"""Render TokyoNight-styled GitHub stats SVG cards into dist/.

Replaces flaky vercel.app-hosted cards (github-readme-stats / github-profile-trophy)
with self-rendered versions built from the GitHub API. Stdlib only.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("CARD_USER", "ZRZRING")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"

BG, TITLE, TEXT, MUTED = "#1a1b26", "#7aa2f7", "#c0caf5", "#565f89"
PURPLE, RED, GREEN, ORANGE = "#bb9af7", "#f7768e", "#9ece6a", "#e0af68"

LANG_COLORS = {
    "Go": "#00ADD8", "TypeScript": "#3178C6", "Lua": "#000080", "C#": "#178600",
    "C": "#555555", "C++": "#f34b7d", "Python": "#3572A5", "JavaScript": "#f1e05a",
    "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051", "Vim Script": "#199f4b",
    "Dockerfile": "#384d54", "Rust": "#dea584", "Java": "#b07219", "Kotlin": "#A97BFF",
    "Vue": "#41b883", "Ruby": "#701516", "PHP": "#4F5D95", "PowerShell": "#012456",
    "Makefile": "#427819", "Nix": "#7e7eff", "Assembly": "#6E4C13", "Batchfile": "#C1F12E",
}


def api(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}", "User-Agent": "profile-cards", "Accept": accept})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def search_count(q, accept="application/vnd.github+json"):
    from urllib.parse import quote
    return api(f"https://api.github.com/search/issues?q={quote(q)}&per_page=1", accept)["total_count"]


def safe(fn, default=0):
    try:
        return fn()
    except Exception as e:  # 单项失败不拖垮整张卡
        print(f"warn: {fn.__name__}: {e}", file=sys.stderr)
        return default


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


def gather():
    d = {}
    user = api(f"https://api.github.com/users/{USER}")
    d["followers"], d["repos"] = user["followers"], user["public_repos"]
    d["years"] = max(1, datetime.now(timezone.utc).year - int(user["created_at"][:4]))

    stars, langs = 0, {}
    page = 1
    while True:
        repos = api(f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}")
        if not repos:
            break
        for r in repos:
            stars += r["stargazers_count"]
            if r["fork"] or r["size"] == 0:
                continue
            try:
                for lang, kb in api(r["languages_url"]).items():
                    langs[lang] = langs.get(lang, 0) + kb
            except Exception:
                pass
        page += 1
    d["stars"], d["langs"] = stars, langs

    d["contribs"] = safe(lambda: gql_contribs())
    d["commits"] = safe(lambda: api(
        "https://api.github.com/search/commits?q=author:" + USER + "&per_page=1")["total_count"], -1)
    d["prs"] = safe(lambda: search_count(f"author:{USER} type:pr is:public"))
    d["issues"] = safe(lambda: search_count(f"author:{USER} type:issue is:public"))
    return d


def gql_contribs():
    q = '{ user(login: "%s") { contributionsCollection { contributionCalendar { totalContributions } } } }' % USER
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": q}).encode(),
                                 headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]


def card_open(w, h, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" rx="12" fill="{BG}"/>'
            f'<text x="28" y="38" font-family="Segoe UI,Ubuntu,sans-serif" font-size="16" '
            f'font-weight="600" fill="{TITLE}">{title}</text>')


def tile(x, y, num, label, accent):
    return (f'<circle cx="{x+6}" cy="{y-2}" r="4" fill="{accent}"/>'
            f'<text x="{x+18}" y="{y+3}" font-family="Segoe UI,Ubuntu,sans-serif" font-size="26" '
            f'font-weight="700" fill="{TEXT}">{num}</text>'
            f'<text x="{x+18}" y="{y+22}" font-family="Segoe UI,Ubuntu,sans-serif" font-size="12" '
            f'fill="{MUTED}">{label}</text>')


def render_stats(d):
    s = card_open(520, 195, f"{USER}'s GitHub Stats")
    s += tile(28, 95, fmt(d["contribs"]), "Contributions (last year)", GREEN)
    s += tile(28, 155, fmt(d["stars"]), "Total Stars", ORANGE)
    s += tile(285, 95, fmt(d["followers"]), "Followers", PURPLE)
    s += tile(285, 155, str(d["repos"]), "Public Repos", RED)
    return s + "</svg>"


def render_langs(d):
    s = card_open(400, 195, "Top Languages")
    langs = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:6]
    total = sum(v for _, v in langs) or 1
    if langs:
        s += ('<clipPath id="langbar"><rect x="28" y="62" width="344" height="10" rx="5"/></clipPath>'
              f'<rect x="28" y="62" width="344" height="10" rx="5" fill="{MUTED}" opacity="0.25"/>')
        x, bar_w = 28, 344
        segs = ""
        for lang, kb in langs:
            w = bar_w * kb / total
            segs += f'<rect x="{x:.1f}" y="62" width="{w+0.5:.1f}" height="10" fill="{LANG_COLORS.get(lang, "#7aa2f7")}"/>'
            x += w
        s += f'<g clip-path="url(#langbar)">{segs}</g>'
        col_x, col_y = [28, 216], 105
        for i, (lang, kb) in enumerate(langs):
            cx, cy = col_x[i % 2], col_y + (i // 2) * 28
            pct = kb / total * 100
            pct_s = f"{pct:.0f}%" if pct >= 1 else "<1%"
            color = LANG_COLORS.get(lang, "#7aa2f7")
            s += (f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{color}"/>'
                  f'<text x="{cx+18}" y="{cy}" font-family="Segoe UI,Ubuntu,sans-serif" '
                  f'font-size="13" fill="{TEXT}">{lang}</text>'
                  f'<text x="{cx+178}" y="{cy}" font-family="Segoe UI,Ubuntu,sans-serif" '
                  f'font-size="12" fill="{MUTED}" text-anchor="end">{pct_s}</text>')
    return s + "</svg>"


def render_highlights(d):
    s = card_open(520, 195, "Contribution Highlights")
    commit_n = str(d["commits"]) if d["commits"] >= 0 else "–"
    s += tile(28, 95, commit_n, "Commits (public)", TITLE)
    s += tile(28, 155, str(d["years"]), "Years on GitHub", ORANGE)
    s += tile(285, 95, fmt(d["prs"]), "Pull Requests", PURPLE)
    s += tile(285, 155, fmt(d["issues"]), "Issues", RED)
    return s + "</svg>"


os.makedirs(OUT, exist_ok=True)
data = gather()
for name, render in [("stats.svg", render_stats), ("top-langs.svg", render_langs),
                     ("highlights.svg", render_highlights)]:
    svg = render(data)
    assert "<svg" in svg
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{name} ok ({len(svg)} bytes)")
