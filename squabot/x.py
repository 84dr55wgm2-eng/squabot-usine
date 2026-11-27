"""Veille 𝕏 : suit des comptes, garde les posts qui buzzent, télécharge leurs vidéos et photos.

Outil libre : gallery-dl (lecture des comptes, photos et vidéos). 𝕏 n'affiche les comptes qu'aux personnes
connectées : la session d'un compte secondaire est lue dans les secrets X_AUTH_TOKEN et X_CT0.

    python -m squabot x suivre            → data/x/<date>.json (posts récents des comptes suivis, notés)
    python -m squabot x telecharger <url> <dossier>   → vidéo ou photos du post dans <dossier>
"""
import datetime, json, os, subprocess, tempfile
from pathlib import Path
import yaml
from . import config


def _conf():
    """Fichier de configuration gallery-dl avec la session 𝕏 (jamais écrit dans le dépôt)."""
    jeton, ct0 = os.environ.get("X_AUTH_TOKEN", "").strip(), os.environ.get("X_CT0", "").strip()
    if not jeton or not ct0:
        raise SystemExit("Session 𝕏 absente : ajouter les secrets X_AUTH_TOKEN et X_CT0.")
    c = {"extractor": {"twitter": {"cookies": {"auth_token": jeton, "ct0": ct0},
                                   "text-tweets": True, "retweets": False, "replies": False,
                                   "conversations": False, "videos": True}}}
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump(c, f); f.close()
    return f.name


def abonnements(moi, conf=None):
    """Comptes suivis par le compte secondaire du bot (sa liste « Abonnements » sur 𝕏)."""
    r = subprocess.run(["gallery-dl", "--config", conf or _conf(), "-j", f"https://x.com/{moi}/following"],
                       capture_output=True, text=True, timeout=300)
    pseudos = []
    try:
        for e in json.loads(r.stdout or "[]"):
            if isinstance(e, list) and len(e) >= 2 and isinstance(e[1], str) and "x.com/" in e[1].replace("twitter.com/", "x.com/"):
                ps = e[1].replace("twitter.com/", "x.com/").split("x.com/")[1].split("/")[0]
                if ps and ps not in ("i", moi) and ps not in pseudos: pseudos.append(ps)
    except json.JSONDecodeError: pass
    if not pseudos: print(f"  abonnements de @{moi} illisibles ({(r.stderr.strip().splitlines() or ['?'])[-1][:160]})", flush=True)
    return pseudos


def comptes_suivis(conf=None):
    """{chaîne: [pseudos]} : sources/x.yaml, plus tous les abonnements du compte secondaire (« a-classer »)."""
    f = config.RACINE / "sources" / "x.yaml"
    c = yaml.safe_load(f.read_text()) if f.exists() else {}
    moi = c.pop("compte_bot", None)
    if moi:
        connus = {p for v in c.values() for p in v}
        nouveaux = [p for p in abonnements(moi, conf) if p not in connus]
        c["a-classer"] = (c.get("a-classer") or []) + nouveaux
        print(f"@{moi} suit {len(nouveaux) + len(connus)} comptes", flush=True)
    return c


def lire_compte(pseudo, n=25, conf=None):
    """Derniers posts d'un compte : texte, date, stats, médias."""
    conf = conf or _conf()
    r = subprocess.run(["gallery-dl", "--config", conf, "-j", "--range", f"1-{n}", f"https://x.com/{pseudo}"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode not in (0, 4) or not r.stdout.strip():
        print(f"  @{pseudo} : lecture impossible ({(r.stderr.strip().splitlines() or ['?'])[-1][:160]})", flush=True)
        return []
    posts = {}
    for entree in json.loads(r.stdout):
        if not isinstance(entree, list) or len(entree) < 2: continue
        m = entree[-1] if isinstance(entree[-1], dict) else {}
        tid = str(m.get("tweet_id") or "")
        if not tid: continue
        p = posts.setdefault(tid, {
            "id": tid, "compte": pseudo, "url": f"https://x.com/{pseudo}/status/{tid}",
            "date": str(m.get("date", "")), "texte": m.get("content", ""), "langue": m.get("lang", ""),
            "likes": m.get("favorite_count", 0), "reposts": m.get("retweet_count", 0),
            "reponses": m.get("reply_count", 0), "vues": m.get("view_count", 0), "medias": []})
        if entree[0] == 3 and isinstance(entree[1], str):          # 3 = un fichier (photo ou vidéo)
            p["medias"].append({"type": "video" if m.get("extension") == "mp4" else "photo",
                                "url": entree[1], "duree": m.get("duration")})
    return list(posts.values())


def noter(p):
    """Buzz : interactions rapportées à l'âge du post (les vidéos comptent double pour nos montages)."""
    try: age = max(1, (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(p["date"][:19])).total_seconds() / 3600)
    except ValueError: age = 24
    inter = p["likes"] + 3 * p["reposts"] + 2 * p["reponses"] + (p["vues"] or 0) / 100
    bonus = 2 if any(m["type"] == "video" for m in p["medias"]) else 1.3 if p["medias"] else 1
    return round(inter / age ** 0.8 * bonus, 1)


def suivre():
    conf, tout = _conf(), []
    for groupe, pseudos in comptes_suivis(conf).items():
        for ps in pseudos:
            posts = lire_compte(ps, n=20, conf=conf)
            for p in posts: p["groupe"] = groupe; p["buzz"] = noter(p)
            print(f"  @{ps} : {len(posts)} posts, {sum(1 for p in posts if p['medias'])} avec médias", flush=True)
            tout += posts
    tout.sort(key=lambda p: -p["buzz"])
    sortie = config.RACINE / "data" / "x" / f"{datetime.date.today()}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(tout, ensure_ascii=False, indent=1))
    print(f"{len(tout)} posts → {sortie}", flush=True)
    return tout


def telecharger(url, dossier):
    """Médias d'un post dans <dossier> (vidéos mp4 et photos)."""
    dossier = Path(dossier); dossier.mkdir(parents=True, exist_ok=True)
    conf = _conf()
    subprocess.run(["gallery-dl", "--config", conf, "-D", str(dossier), "-f", "{tweet_id}_{num}.{extension}", url],
                   capture_output=True, text=True, timeout=600)
    return sorted(str(f) for f in dossier.iterdir() if f.suffix.lower() in (".mp4", ".jpg", ".jpeg", ".png", ".webp"))
