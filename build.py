#!/usr/bin/env python3
"""
Construit le site.

1. Regenere index.html a partir des donnees intervals.icu
   (graphique des semaines et compteur depuis janvier 2025).
2. Transforme chaque fichier de content/*.md en page d'article.
3. Reconstruit blog.html, le sommaire classe par thematique.

Variables d'environnement :
  ICU_API_KEY      cle API intervals.icu (Settings > Developer > API key)
  ICU_ATHLETE_ID   identifiant athlete, par defaut i384564

Usage local :
  ICU_API_KEY=xxxx python3 build/build.py
  python3 build/build.py --articles-only   (sans appeler intervals.icu)
"""

import base64
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "build", "templates")
CONTENT = os.path.join(ROOT, "content")
CACHE = os.path.join(ROOT, "build", "cache.json")

ATHLETE = os.environ.get("ICU_ATHLETE_ID", "i384564")
KEY = os.environ.get("ICU_API_KEY", "")

START = dt.date(2024, 12, 2)
HIGHLIGHT = {dt.date(2025, 2, 10), dt.date(2025, 2, 17), dt.date(2026, 8, 24)}
RIDE_TYPES = {"Ride", "GravelRide", "VirtualRide", "MountainBikeRide", "EBikeRide"}

W, H, YMAX = 900.0, 200.0, 1100.0

# ordre d'affichage des thematiques dans le sommaire
THEMES = ["Les données", "Le matériel", "La course", "La nutrition", "Le récit"]

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


# --------------------------------------------------------------------------
# articles
# --------------------------------------------------------------------------

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "article"


def front_matter(raw):
    """Lit l'entete --- cle: valeur --- en tete de fichier."""
    meta, body = {}, raw
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            for line in raw[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = raw[end + 4:].lstrip("\n")
    return meta, body


def to_html(md):
    """Markdown minimal, suffisant pour des articles : titres, gras, italique,
    listes, citations, liens, et blocs HTML bruts laisses tels quels."""
    out, buf, i = [], [], 0
    lines = md.split("\n")
    raw_depth = 0

    def flush():
        if buf:
            text = " ".join(buf).strip()
            if text:
                out.append("<p>" + inline(text) + "</p>")
            buf.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # bloc HTML brut : tout ce qui commence par une balise de bloc
        if raw_depth == 0 and re.match(
            r"<(figure|table|div|svg|section|aside|blockquote|pre|ul|ol|p|h[1-6])\b", stripped
        ):
            flush()
            tag = re.match(r"<(\w+)", stripped).group(1)
            raw = [line]
            depth = stripped.count("<" + tag) - stripped.count("</" + tag)
            if stripped.endswith("/>") or depth <= 0:
                out.append(line)
                i += 1
                continue
            i += 1
            while i < len(lines) and depth > 0:
                raw.append(lines[i])
                depth += lines[i].count("<" + tag) - lines[i].count("</" + tag)
                i += 1
            out.append("\n".join(raw))
            continue

        if not stripped:
            flush()
            i += 1
            continue

        m = re.match(r"(#{2,4})\s+(.*)", stripped)
        if m:
            flush()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        if stripped.startswith("> "):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote.append(lines[i].strip()[2:])
                i += 1
            out.append('<p class="pull">' + inline(" ".join(quote)) + "</p>")
            continue

        if re.match(r"[-*]\s+", stripped):
            flush()
            items = []
            while i < len(lines) and re.match(r"[-*]\s+", lines[i].strip()):
                items.append("<li>" + inline(re.sub(r"^[-*]\s+", "", lines[i].strip())) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        buf.append(stripped)
        i += 1

    flush()
    return "\n    ".join(out)


def inline(t):
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r'<span class="num">\1</span>', t)
    return t


def read_articles():
    posts = []
    if not os.path.isdir(CONTENT):
        return posts
    for name in sorted(os.listdir(CONTENT)):
        if not name.endswith(".md") or name.startswith("_"):
            continue
        raw = open(os.path.join(CONTENT, name), encoding="utf-8").read()
        meta, body = front_matter(raw)
        if not meta.get("titre"):
            print(f"  {name} ignore : pas de champ titre", file=sys.stderr)
            continue
        date = dt.date.fromisoformat(meta.get("date", name[:10]))
        posts.append({
            "titre": meta["titre"],
            "theme": meta.get("theme", "Les données"),
            "resume": meta.get("resume", ""),
            "date": date,
            "slug": meta.get("slug") or slugify(meta["titre"]),
            "body": to_html(body),
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def fr_date(d):
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def build_articles(posts):
    tpl = open(os.path.join(TPL, "article.html"), encoding="utf-8").read()
    for p in posts:
        page = (tpl
                .replace("{{TITLE}}", html.escape(p["titre"]))
                .replace("{{THEME}}", html.escape(p["theme"]))
                .replace("{{DATE}}", fr_date(p["date"]))
                .replace("{{STANDFIRST}}", p["resume"])
                .replace("{{BODY}}", p["body"]))
        with open(os.path.join(ROOT, p["slug"] + ".html"), "w", encoding="utf-8") as f:
            f.write(wrap(page, p["titre"]))


def build_blog(posts):
    tpl = open(os.path.join(TPL, "blog.html"), encoding="utf-8").read()
    themes = THEMES + sorted({p["theme"] for p in posts} - set(THEMES))
    blocks = []
    for theme in themes:
        sel = [p for p in posts if p["theme"] == theme]
        if not sel:
            continue
        rows = "".join(
            f'\n      <div class="post-row">'
            f'<time datetime="{p["date"].isoformat()}">{fr_date(p["date"])}</time>'
            f'<div><h3><a href="{p["slug"]}.html">{html.escape(p["titre"])}</a></h3>'
            f'<p>{p["resume"]}</p></div></div>'
            for p in sel
        )
        n = len(sel)
        blocks.append(
            f'  <section class="theme-band col">\n'
            f'    <h2>{html.escape(theme)}</h2>\n'
            f'    <span class="count">{n} article{"s" if n > 1 else ""}</span>\n'
            f'    <div class="posts">{rows}\n    </div>\n'
            f'  </section>'
        )
    page = tpl.replace("{{THEMES}}", "\n".join(blocks)).replace("{{COUNT}}", str(len(posts)))
    with open(os.path.join(ROOT, "blog.html"), "w", encoding="utf-8") as f:
        f.write(wrap(page, "Le carnet"))


# --------------------------------------------------------------------------
# page principale et donnees intervals.icu
# --------------------------------------------------------------------------

def fetch():
    if not KEY:
        print("ICU_API_KEY absente, utilisation du cache", file=sys.stderr)
        return load_cache()
    url = (f"https://intervals.icu/api/v1/athlete/{ATHLETE}/activities"
           f"?oldest={START.isoformat()}&newest={dt.date.today().isoformat()}")
    token = base64.b64encode(f"API_KEY:{KEY}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
    except Exception as e:  # reseau, auth, format
        print(f"intervals.icu injoignable ({e}), utilisation du cache", file=sys.stderr)
        return load_cache()
    rows = [{"date": (a.get("start_date_local") or "")[:10],
             "km": (a.get("distance") or 0) / 1000.0,
             "sec": a.get("moving_time") or 0}
            for a in data if a.get("type") in RIDE_TYPES]
    rows = [r for r in rows if r["date"]]
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(rows, f)
    return rows


def load_cache():
    if os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    return None


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def weekly(rows):
    end = monday(dt.date.today())
    buckets, w = {}, START
    while w <= end:
        buckets[w] = 0.0
        w += dt.timedelta(days=7)
    for r in rows:
        m = monday(dt.date.fromisoformat(r["date"]))
        if m in buckets:
            buckets[m] += r["km"]
    return sorted(buckets.items())


def build_index(rows):
    weeks = weekly(rows)
    n = len(weeks)
    step = W / n
    bw = step * 0.84
    top = max(YMAX, max(v for _, v in weeks))
    bars = "\n        ".join(
        f'<rect class="{"b hl" if w in HIGHLIGHT else "b"}" x="{i*step:.1f}" '
        f'y="{H - max(0.8, km/top*H):.1f}" width="{bw:.1f}" height="{max(0.8, km/top*H):.1f}"/>'
        for i, (w, km) in enumerate(weeks))

    axis = [f'<text x="0" y="-9">{f"{top:,.0f}".replace(",", chr(8239))} km / semaine</text>']
    seen = set()
    for i, (w, _) in enumerate(weeks):
        if w.year not in seen:
            seen.add(w.year)
            if i * step < W - 40:
                axis.append(f'<text x="{i*step:.0f}" y="214">{w.year}</text>')

    since = dt.date(2025, 1, 1)
    sel = [r for r in rows if dt.date.fromisoformat(r["date"]) >= since]
    tot_km = sum(r["km"] for r in sel)
    tot_h = sum(r["sec"] for r in sel) / 3600.0
    peak = max(weeks, key=lambda x: x[1])
    alt = (f"Volume hebdomadaire de vélo depuis décembre 2024. Semaine la plus forte : "
           f"{peak[1]:.0f} km. {sum(1 for _, v in weeks if v < 1)} semaines sans vélo.")

    page = open(os.path.join(TPL, "index.html"), encoding="utf-8").read()
    page = (page.replace("{{BARS}}", bars)
                .replace("{{AXIS}}", "\n        ".join(axis))
                .replace("{{CHART_ALT}}", alt)
                .replace("{{TOTAL_KM}}", f"{tot_km:,.0f}".replace(",", " "))
                .replace("{{TOTAL_H}}", f"{tot_h:,.0f}".replace(",", " "))
                .replace("{{UPDATED}}", fr_date(dt.date.today())))
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(wrap(page, "De Honfleur aux Badlands"))
    print(f"index.html : {n} semaines, {tot_km:.0f} km, {tot_h:.0f} h")


# --------------------------------------------------------------------------

def wrap(fragment, title):
    m = re.search(r"<title>(.*?)</title>\s*", fragment, re.S)
    if m:
        title = m.group(1).strip()
        fragment = fragment[:m.start()] + fragment[m.end():]
    head = ('<!doctype html>\n<html lang="fr">\n<head>\n'
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{title}</title>\n'
            f'<meta name="description" content="{title} — Ludovic Laidié, ultra gravel, Honfleur.">\n'
            '<meta property="og:type" content="article">\n'
            f'<meta property="og:title" content="{title}">\n'
            '<meta property="og:image" content="img/nuit.jpg">\n'
            '</head>\n<body>\n')
    return head + fragment + "\n</body>\n</html>\n"


def main():
    posts = read_articles()
    build_articles(posts)
    build_blog(posts)
    print(f"{len(posts)} articles, blog.html reconstruit")

    if "--articles-only" in sys.argv:
        return
    rows = fetch()
    if rows is None:
        print("pas de donnees intervals.icu : index.html laisse tel quel. "
              "Renseigne le secret ICU_API_KEY pour activer la mise a jour.",
              file=sys.stderr)
        return
    build_index(rows)


if __name__ == "__main__":
    main()
