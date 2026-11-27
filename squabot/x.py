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
            if isinstance(e, list) and len(e) >= 3 and e[0] == 6 and isinstance(e[2], dict):
                u = e[2]; core = u.get("core") or {}
                ps = core.get("screen_name") or (f"id:{u['rest_id']}" if u.get("rest_id") else "")
                bio = (u.get("profile_bio") or {}).get("description", "") if isinstance(u.get("profile_bio"), dict) else ""
                if ps and ps != moi and ps not in [x["pseudo"] for x in pseudos]:
                    pseudos.append({"pseudo": ps, "nom": core.get("name", ""), "bio": bio})
    except json.JSONDecodeError: pass
    if not pseudos: print(f"  abonnements de @{moi} illisibles ({(r.stderr.strip().splitlines() or ['?'])[-1][:160]})", flush=True)
    return pseudos


# Catégories de veille en plus des thèmes de chaînes (pour ranger tout ce qui passe sur 𝕏 sans tout mélanger).
AUTRES = {
    "musique": "rap, musique, albums, clips, artistes, concerts, classements Spotify",
    "streaming": "Twitch, Kick, streamers, clips de live, drama entre streamers, événements en direct",
    "actualite": "actualité, politique, économie, société, informations du jour, alertes",
    "humour": "memes, humour, vidéos drôles, buzz absurde, trends",
    "people": "célébrités, télé-réalité, influenceurs, rumeurs, couples de stars",
    "football": "football, transferts, matchs, joueurs, Ligue 1, Ligue des champions",
}
# Mots typiques de 𝕏 qui aident à reconnaître un thème.
ENRICHI = {
    "jeux-video": "GTA 6, Rockstar, gameplay, PS5, Xbox, Nintendo Switch, Fortnite, Call of Duty, patch, trailer, joueurs, mission, console",
    "anime": "anime, manga, Jujutsu Kaisen, One Piece, Naruto, épisode, saison, chapitre, studio, opening",
    "automobile": "voiture réelle, constructeur, essai auto, moteur, supercar, Formule 1, salon automobile",
    "cinema-series": "film, série, Netflix, bande-annonce, box-office, acteur, réalisateur, saison",
    "sport": "match, équipe, championnat, NBA, MMA, tennis, Jeux olympiques",
    "tech-ia": "technologie, IA, ChatGPT, Apple, smartphone, startup, application",
}
SEUIL = 0.30


def _modele():
    from fastembed import TextEmbedding
    return TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


def _vecteurs(m, textes):
    import numpy as np
    e = np.array(list(m.embed(textes))); return e / np.linalg.norm(e, axis=1, keepdims=True)


def categories():
    """{id: texte descriptif} : thèmes des chaînes + catégories de veille."""
    c = {}
    for tid, t in config.themes().items():
        c[tid] = f"{t.get('nom', tid)} : {ENRICHI.get(tid, '')}. {t.get('description', '')} {' '.join(t.get('mots_cles', []))}"
    for k, v in AUTRES.items(): c.setdefault(k, f"{k} : {v}")
    return c


def classer(comptes, posts_par_compte, m=None):
    """Range chaque compte dans la catégorie la plus proche de sa bio et de ses derniers posts (multilingue)."""
    cats = categories(); ids = list(cats)
    m = m or _modele(); C = _vecteurs(m, [cats[i] for i in ids])
    for ps, info in comptes.items():
        if info.get("force"): continue
        import numpy as np
        textes = [p["texte"][:300].lower() for p in posts_par_compte.get(ps, []) if len(p.get("texte", "")) > 15][:15]
        textes += [f"{ps} {info.get('nom', '')}. {info.get('bio', '')}"] * 3
        if not textes: continue
        S = _vecteurs(m, textes) @ C.T                  # chaque post vote pour sa catégorie
        votes = np.zeros(len(ids))
        for ligne in S: votes[ligne.argmax()] += 1
        sc = votes / len(textes) * 0.5 + S.mean(0)       # majorité des posts + proximité moyenne
        ordre = sc.argsort()[::-1]
        info["theme"] = ids[ordre[0]] if sc[ordre[0]] >= SEUIL else "divers"
        info["score"] = round(float(sc[ordre[0]]), 3)
        info["votes"] = int(votes[ordre[0]])
        info["second"] = ids[ordre[1]]
    return comptes


def ranger_posts(posts, m=None, seuil=0.42):
    """Chaque post a son propre thème quand il est net (un compte rap qui parle de GTA 6 → jeux-video)."""
    cats = categories(); ids = list(cats)
    avec = [p for p in posts if len(p.get("texte", "")) > 20]
    if not avec: return
    m = m or _modele(); S = _vecteurs(m, [p["texte"][:300].lower() for p in avec]) @ _vecteurs(m, [cats[i] for i in ids]).T
    for p, ligne in zip(avec, S):
        if ligne.max() >= seuil: p["theme"] = ids[int(ligne.argmax())]


def comptes_suivis(conf=None):
    """{pseudo: info} : abonnements du compte du bot (data/x/comptes.json garde catégorie et dernière lecture).
    sources/x.yaml peut réserver des comptes à une chaîne : leur catégorie est alors le thème de la chaîne."""
    f = config.RACINE / "sources" / "x.yaml"
    c = yaml.safe_load(f.read_text()) if f.exists() else {}
    etat_f = config.RACINE / "data" / "x" / "comptes.json"
    etat = json.loads(etat_f.read_text()) if etat_f.exists() else {}
    moi = c.pop("compte_bot", None)
    if moi:
        for a in abonnements(moi, conf):
            e = etat.setdefault(a["pseudo"], {}); e.update(nom=a["nom"], bio=a["bio"])
    chaines = config.comptes()
    for chaine, pseudos in c.items():
        for ps in pseudos or []:
            e = etat.setdefault(ps, {}); e["force"] = True
            e["theme"] = (chaines.get(chaine) or {}).get("theme", chaine); e["chaine"] = chaine
    print(f"@{moi} : {len(etat)} comptes suivis", flush=True)
    return etat, etat_f


def lire_compte(pseudo, n=25, conf=None):
    """Derniers posts d'un compte : texte, date, stats, médias."""
    conf = conf or _conf()
    r = subprocess.run(["gallery-dl", "--config", conf, "-j", "--range", f"1-{n}", f"https://x.com/{pseudo}/tweets"],
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
            "id": tid, "compte": (m.get("author") or {}).get("name", pseudo), "url": f"https://x.com/{(m.get('author') or {}).get('name', 'i')}/status/{tid}",
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


def suivre(par_passage=int(os.environ.get("SQUABOT_X_PAR_PASSAGE", 60))):
    """Lit les comptes les moins récemment lus (par_passage à chaque fois : prudence avec 𝕏), les classe, note les posts."""
    conf = _conf()
    etat, etat_f = comptes_suivis(conf)
    a_lire = sorted(etat, key=lambda p: etat[p].get("lu_le", ""))[:par_passage]
    lus = {}
    for ps in a_lire:
        posts = lire_compte(ps, n=20, conf=conf)
        etat[ps]["lu_le"] = datetime.datetime.utcnow().isoformat(timespec="minutes")
        lus[ps] = posts
        print(f"  @{ps} : {len(posts)} posts, {sum(1 for p in posts if p['medias'])} avec médias", flush=True)
    try:
        m = _modele(); classer({p: etat[p] for p in lus}, lus, m)
        ranger_posts([q for l in lus.values() for q in l], m)
    except Exception as e: print("  classement impossible :", e, flush=True)
    sortie = config.RACINE / "data" / "x" / f"{datetime.date.today()}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tout = {p["id"]: p for p in (json.loads(sortie.read_text()) if sortie.exists() else [])}
    for ps, posts in lus.items():
        for p in posts:
            p["theme_compte"] = etat[ps].get("theme", "divers")
            if etat[ps].get("force") or not p.get("theme"): p["theme"] = p["theme_compte"]
            p["buzz"] = noter(p)
            if etat[ps].get("chaine"): p["chaine"] = etat[ps]["chaine"]
            tout[p["id"]] = p
    tout = sorted(tout.values(), key=lambda p: -p["buzz"])
    sortie.write_text(json.dumps(tout, ensure_ascii=False, indent=1))
    etat_f.write_text(json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True))
    par = {}
    for ps in lus: par.setdefault(etat[ps].get("theme", "divers"), []).append(ps)
    for th, l in sorted(par.items()): print(f"  {th} : {', '.join('@' + x for x in l)}", flush=True)
    print(f"{len(tout)} posts → {sortie}", flush=True)
    return tout


def telecharger(url, dossier):
    """Médias d'un post dans <dossier> (vidéos mp4 et photos)."""
    dossier = Path(dossier); dossier.mkdir(parents=True, exist_ok=True)
    conf = _conf()
    subprocess.run(["gallery-dl", "--config", conf, "-D", str(dossier), "-f", "{tweet_id}_{num}.{extension}", url],
                   capture_output=True, text=True, timeout=600)
    return sorted(str(f) for f in dossier.iterdir() if f.suffix.lower() in (".mp4", ".jpg", ".jpeg", ".png", ".webp"))
