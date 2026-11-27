"""Veille du monde, sans Claude : pour chaque thème, des sujets candidats frais et populaires.

Sources gratuites et sans clé : Google Actualités (RSS), Reddit (JSON public), Wikipédia (« ce jour-là »
et articles les plus lus), YouTube (recherche par yt-dlp, métadonnées seulement).
Résultat : data/veille/<date>/<thème>.json, lu par Claude pendant sa tournée de nuit.
"""
import datetime as dt, json, re, subprocess, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from . import config

UA = {"User-Agent": "squabot/0.2 (veille de sujets pour une chaine video)"}


def _get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def google_actus(requete, langue="fr", n=10):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": requete + " when:7d", "hl": langue, "gl": "FR", "ceid": "FR:fr"})
    out = []
    for it in ET.fromstring(_get(url)).iter("item"):
        out.append({"source": "google-actus", "titre": it.findtext("title"), "lien": it.findtext("link"),
                    "date": it.findtext("pubDate"), "requete": requete})
    return out[:n]


def reddit(communaute, periode="day", n=10):
    """Reddit bloque souvent les serveurs de GitHub : flux RSS, puis archive publique Arctic Shift en secours."""
    for f in (_reddit_json, _reddit_rss, _reddit_arctic):
        try:
            r = f(communaute, periode, n)
            if r: return r
        except Exception as e:
            derniere = e
    raise derniere


def _reddit_rss(communaute, periode, n):
    ns = {"a": "http://www.w3.org/2005/Atom"}
    racine = ET.fromstring(_get(f"https://www.reddit.com/r/{communaute}/top/.rss?t={periode}&limit={n}"))
    return [{"source": f"reddit/{communaute}", "titre": e.findtext("a:title", namespaces=ns),
             "lien": (e.find("a:link", ns).attrib.get("href") if e.find("a:link", ns) is not None else None),
             "texte": re.sub(r"<[^>]+>", " ", e.findtext("a:content", default="", namespaces=ns))[:1500]}
            for e in racine.findall("a:entry", ns)]


def _reddit_arctic(communaute, periode, n):
    apres = (dt.date.today() - dt.timedelta(days=2 if periode == "day" else 8)).isoformat()
    d = json.loads(_get("https://arctic-shift.photon-reddit.com/api/posts/search?" + urllib.parse.urlencode(
        {"subreddit": communaute, "after": apres, "limit": 100, "sort": "desc"})))
    posts = sorted(d.get("data", []), key=lambda p: -(p.get("score") or 0))
    return [{"source": f"reddit/{communaute}", "titre": p.get("title"), "lien": "https://www.reddit.com" + (p.get("permalink") or ""),
             "score": p.get("score"), "texte": (p.get("selftext") or "")[:1500]}
            for p in posts if not p.get("over_18")][:n]


def _reddit_json(communaute, periode="day", n=10):
    d = json.loads(_get(f"https://www.reddit.com/r/{communaute}/top.json?t={periode}&limit={n}"))
    out = []
    for c in d.get("data", {}).get("children", []):
        p = c["data"]
        if p.get("over_18") or p.get("stickied"): continue
        out.append({"source": f"reddit/{communaute}", "titre": p["title"], "lien": "https://www.reddit.com" + p["permalink"],
                    "score": p.get("score", 0), "commentaires": p.get("num_comments", 0),
                    "texte": (p.get("selftext") or "")[:1500]})
    return out


def wikipedia_ce_jour(langue="fr"):
    j = dt.date.today()
    d = json.loads(_get(f"https://api.wikimedia.org/feed/v1/wikipedia/{langue}/onthisday/events/{j.month:02d}/{j.day:02d}"))
    return [{"source": "wikipedia-ce-jour", "titre": f"{e.get('year')} : {e.get('text')}",
             "lien": (e.get("pages") or [{}])[0].get("content_urls", {}).get("desktop", {}).get("page")} for e in d.get("events", [])[:25]]


def wikipedia_plus_lus(langue="fr", n=25):
    j = dt.date.today() - dt.timedelta(days=1)
    d = json.loads(_get(f"https://api.wikimedia.org/feed/v1/wikipedia/{langue}/featured/{j:%Y/%m/%d}"))
    arts = (d.get("mostread") or {}).get("articles", [])
    return [{"source": "wikipedia-plus-lus", "titre": a.get("normalizedtitle"), "vues": a.get("views"),
             "resume": (a.get("extract") or "")[:400], "lien": a.get("content_urls", {}).get("desktop", {}).get("page")}
            for a in arts[:n] if ":" not in (a.get("title") or "")]


def youtube(requete, n=10):
    """Ce qui marche déjà sur YouTube pour ce sujet : titres, vues, durées (aucun téléchargement de vidéo)."""
    r = subprocess.run(["yt-dlp", "--flat-playlist", "--dump-json", "--no-warnings", "--extractor-args", "youtube:lang=fr", f"ytsearch{n}:{requete}"],
                       capture_output=True, text=True, timeout=120)
    out = []
    for ligne in r.stdout.splitlines():
        try: v = json.loads(ligne)
        except ValueError: continue
        out.append({"source": "youtube", "titre": v.get("title"), "lien": v.get("url") or v.get("webpage_url"),
                    "vues": v.get("view_count"), "duree": v.get("duration"), "chaine": v.get("channel"), "requete": requete})
    return out


def rss(url, n=15):
    """N'importe quel flux RSS ou Atom (site d'actualité, blog, ou RSSHub pour les sites qui n'en ont pas)."""
    racine = ET.fromstring(_get(url)); a = "{http://www.w3.org/2005/Atom}"
    items = list(racine.iter("item")) or list(racine.iter(a + "entry"))
    out = []
    for it in items[:n]:
        lien = it.findtext("link") or (it.find(a + "link").attrib.get("href") if it.find(a + "link") is not None else None)
        out.append({"source": f"rss/{urllib.parse.urlparse(url).netloc}", "titre": it.findtext("title") or it.findtext(a + "title"),
                    "lien": lien, "resume": re.sub(r"<[^>]+>", " ", it.findtext("description") or it.findtext(a + "summary") or "")[:400]})
    return out


def youtube_chaine(chaine, n=15):
    """Dernières vidéos d'une chaîne qui marche : titres et vues, pour s'inspirer des formats (jamais du contenu)."""
    url = chaine if chaine.startswith("http") else f"https://www.youtube.com/{chaine if chaine.startswith('@') else '@' + chaine}/videos"
    r = subprocess.run(["yt-dlp", "--flat-playlist", "--dump-json", "--no-warnings", "--extractor-args", "youtube:lang=fr", "--playlist-end", str(n), url],
                       capture_output=True, text=True, timeout=120)
    out = []
    for ligne in r.stdout.splitlines():
        try: v = json.loads(ligne)
        except ValueError: continue
        out.append({"source": f"youtube-chaine/{chaine}", "titre": v.get("title"), "lien": v.get("url"),
                    "vues": v.get("view_count"), "duree": v.get("duration")})
    return out


def veiller(theme_id, theme, extra=None):
    tout, erreurs = [], []
    def essai(nom, f, *a):
        try: tout.extend(f(*a))
        except Exception as e: erreurs.append(f"{nom} : {str(e)[:120]}")
        time.sleep(1.5)
    extra = extra or {}
    for s in theme.get("sources", []) + extra.get("sources", []):
        if s.get("type") == "reddit":
            for c in s.get("communautes", []): essai(f"reddit/{c}", reddit, c)
        elif s.get("type") == "wikipedia-ce-jour-la":
            essai("wikipedia-ce-jour", wikipedia_ce_jour)
        elif s.get("type") == "wikipedia-article":
            essai("wikipedia-plus-lus", wikipedia_plus_lus)
        elif s.get("type") == "rss":
            essai(f"rss/{s['url'][:40]}", rss, s["url"])
        elif s.get("type") == "youtube-chaine":
            essai(f"youtube-chaine/{s['chaine']}", youtube_chaine, s["chaine"])
    for m in theme.get("mots_cles", []) + extra.get("mots_cles", []):
        essai(f"google/{m}", google_actus, m)
        essai(f"youtube/{m}", youtube, m)
    vus, uniques = set(), []
    for x in tout:
        cle = re.sub(r"\W+", "", (x.get("titre") or "").lower())[:80]
        if cle and cle not in vus: vus.add(cle); uniques.append(x)
    return {"theme": theme_id, "date": dt.datetime.utcnow().isoformat(timespec="minutes") + "Z",
            "candidats": uniques, "erreurs": erreurs}


def tout_veiller():
    jour = dt.date.today().isoformat()
    dossier = config.RACINE / "data" / "veille" / jour
    dossier.mkdir(parents=True, exist_ok=True)
    themes = config.themes()
    for cid, c in config.comptes().items():
        if not c.get("actif") or c.get("theme") not in themes: continue
        r = veiller(c["theme"], themes[c["theme"]], c)
        r["compte"] = cid
        (dossier / f"{cid}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
        print(f"{cid} : {len(r['candidats'])} sujets, {len(r['erreurs'])} source(s) en échec", flush=True)
        for e in r["erreurs"]: print("   ", e, flush=True)
