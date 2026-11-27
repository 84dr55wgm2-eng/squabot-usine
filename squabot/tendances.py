"""Le buzz du moment, toutes plateformes : ce dont le pays parle maintenant.
Sources gratuites sans clé : Google Trends, Google Actus (à la une), tendances 𝕏 (trends24), YouTube tendances (kworb),
Wikipédia (articles les plus lus), Reddit (populaire), TikTok Creative Center (hashtags), Twitch (chaînes en direct).
Chaque source peut tomber : on garde ce qui répond. Résultat : data/tendances/<date>.json (sujets classés par buzz)."""
import datetime as dt, html, json, re, unicodedata, urllib.parse, xml.etree.ElementTree as ET
from . import config
from .veille import _get, wikipedia_plus_lus

PAYS = {"fr": ("FR", "france"), "en": ("US", "united-states"), "es": ("ES", "spain")}
POIDS = {"google-trends": 3.0, "x": 2.0, "youtube": 2.5, "tiktok": 2.5, "google-actus": 1.5, "wikipedia": 1.5, "reddit": 1.0, "twitch": 1.5}
VIDES = set("le la les un une des de du d l et a à au aux en pour par sur dans avec sans est sont qui que quoi the of to in on for and is are with "
            "el los las y por con se su ce cette ces il elle on nous vous ils plus pas ne après avant contre vs".split())


def mots(t):
    t = unicodedata.normalize("NFD", (t or "").lower()); t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return {m for m in re.findall(r"[a-z0-9]{3,}", t) if m not in VIDES}


def google_trends(geo="FR"):
    r = ET.fromstring(_get(f"https://trends.google.com/trending/rss?geo={geo}"))
    ns = {"ht": "https://trends.google.com/trending/rss"}
    out = []
    for i, it in enumerate(r.iter("item")):
        trafic = re.sub(r"\D", "", it.findtext("ht:approx_traffic", "", ns)) or "0"
        out.append({"source": "google-trends", "sujet": it.findtext("title"), "rang": i, "volume": int(trafic),
                    "contexte": [n.findtext("ht:news_item_title", "", ns) for n in it.findall("ht:news_item", ns)][:2]})
    return out


def google_une(langue="fr"):
    pays = PAYS.get(langue, PAYS["fr"])[0]
    r = ET.fromstring(_get(f"https://news.google.com/rss?hl={langue}&gl={pays}&ceid={pays}:{langue}"))
    return [{"source": "google-actus", "sujet": re.sub(r"\s+-\s+[^-]+$", "", it.findtext("title") or ""), "rang": i, "lien": it.findtext("link")}
            for i, it in enumerate(r.iter("item")) if i < 40]


def x_tendances(pays="france"):
    h = _get(f"https://trends24.in/{pays}/").decode("utf-8", "ignore")
    bloc = h.split('class="trend-card__list"', 2)[1] if 'class="trend-card__list"' in h else h   # heure la plus récente
    noms = re.findall(r'class=trend-link[^>]*>([^<]+)<|class="trend-link"[^>]*>([^<]+)<', bloc)
    noms = [html.unescape(a or b).strip() for a, b in noms][:40]
    return [{"source": "x", "sujet": n, "rang": i} for i, n in enumerate(noms)]


def youtube_tendances(geo="FR"):
    h = _get(f"https://kworb.net/youtube/trending/{geo.lower()}.html").decode("utf-8", "ignore")
    out = []
    for i, (vid, titre) in enumerate(re.findall(r'href="(?:\.\./)*video/([\w-]{11})\.html">([^<]+)</a>', h)[:50]):
        out.append({"source": "youtube", "sujet": html.unescape(titre), "rang": i, "lien": f"https://www.youtube.com/watch?v={vid}"})
    return out


def wikipedia(langue="fr"):
    return [{"source": "wikipedia", "sujet": a["titre"], "rang": i, "volume": a.get("vues") or 0, "lien": a.get("lien")}
            for i, a in enumerate(wikipedia_plus_lus(langue, 40))]


def reddit_populaire(geo="FR"):
    d = json.loads(_get(f"https://www.reddit.com/r/popular/hot.json?geo_filter={geo}&limit=50"))
    return [{"source": "reddit", "sujet": c["data"]["title"], "rang": i, "volume": c["data"].get("ups", 0),
             "lien": "https://www.reddit.com" + c["data"]["permalink"]} for i, c in enumerate(d["data"]["children"])]


def tiktok_hashtags(geo="FR"):
    u = ("https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list?"
         + urllib.parse.urlencode({"page": 1, "limit": 50, "period": 7, "country_code": geo, "sort_by": "popular"}))
    d = json.loads(_get(u, entetes={"Referer": "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/fr"}))
    return [{"source": "tiktok", "sujet": "#" + h["hashtag_name"], "rang": i, "volume": h.get("video_views") or h.get("publish_cnt") or 0}
            for i, h in enumerate((d.get("data") or {}).get("list", []))]


def twitch_fr():
    h = _get("https://twitchtracker.com/channels/live/french").decode("utf-8", "ignore")
    noms = re.findall(r'<a href="/([A-Za-z0-9_]{3,25})">\s*([^<]{2,40})</a>', h)
    vus, out = set(), []
    for login, nom in noms:
        if login in vus or login in ("channels", "games", "statistics"): continue
        vus.add(login); out.append({"source": "twitch", "sujet": nom.strip(), "rang": len(out), "lien": f"https://www.twitch.tv/{login}"})
    return out[:30]


def collecter(langue="fr"):
    geo, nom_pays = PAYS.get(langue, PAYS["fr"])
    sources = [("google-trends", google_trends, geo), ("google-actus", google_une, langue), ("x", x_tendances, nom_pays),
               ("youtube", youtube_tendances, geo), ("wikipedia", wikipedia, langue), ("reddit", reddit_populaire, geo),
               ("tiktok", tiktok_hashtags, geo)] + ([("twitch", twitch_fr, None)] if langue == "fr" else [])
    items, etat = [], {}
    for nom, f, arg in sources:
        try:
            r = f(arg) if arg is not None else f(); items += r; etat[nom] = len(r)
        except Exception as e:
            etat[nom] = "échec : " + str(e)[:100]
    return items, etat


def classer(items):
    """Regroupe les sujets qui se recoupent d'une plateforme à l'autre : un sujet présent partout est un vrai buzz."""
    groupes = []
    for it in items:
        m = mots(it["sujet"]) | set().union(*[mots(c) for c in it.get("contexte", [])]) if it.get("contexte") else mots(it["sujet"])
        if not m: continue
        it["_mots"] = m
        base = POIDS.get(it["source"], 1.0) * (1.0 / (1 + it["rang"] / 10))
        for g in groupes:
            if len(m & g["mots"]) >= min(2, len(m), len(g["mots"])) and (len(m) > 1 or m <= g["mots"]):
                g["items"].append(it); g["mots"] |= m; g["score"] += base; break
        else:
            groupes.append({"mots": set(m), "items": [it], "score": base})
    out = []
    for g in groupes:
        plateformes = sorted({i["source"] for i in g["items"]})
        score = g["score"] * (1 + 0.6 * (len(plateformes) - 1))       # bonus multi-plateformes
        tete = max(g["items"], key=lambda i: POIDS.get(i["source"], 1) / (1 + i["rang"]))
        out.append({"sujet": tete["sujet"], "score": round(score, 2), "plateformes": plateformes,
                    "mots": sorted(g["mots"])[:12], "exemples": [{k: i.get(k) for k in ("source", "sujet", "lien") if i.get(k)} for i in g["items"][:5]]})
    return sorted(out, key=lambda x: -x["score"])


def tout(langues=None):
    langues = langues or sorted({c.get("langue", "fr") for c in config.comptes().values() if c.get("actif")} or {"fr"})
    jour = dt.date.today().isoformat()
    dossier = config.RACINE / "data" / "tendances"; dossier.mkdir(parents=True, exist_ok=True)
    resultat = {"date": dt.datetime.utcnow().isoformat(timespec="minutes") + "Z", "langues": {}}
    for l in langues:
        items, etat = collecter(l)
        resultat["langues"][l] = {"sources": etat, "sujets": classer(items)[:80]}
        print(l, etat, flush=True)
        for s in resultat["langues"][l]["sujets"][:12]: print(f"  {s['score']:6.2f} {'+'.join(s['plateformes']):32s} {s['sujet'][:70]}", flush=True)
    (dossier / f"{jour}.json").write_text(json.dumps(resultat, ensure_ascii=False, indent=1))
    return resultat
