"""Fabrication d'une vidéo à partir de son fichier video.json : voix, calage, images, rendu, son, miniature."""
import os
import hashlib, json, subprocess, time
from pathlib import Path
from . import config, voix, images, son, miniature
from .rendu import Rendu, W, H, FPS


def lire(dossier):
    return json.loads((Path(dossier) / "video.json").read_text())


def ecrire(dossier, v):
    v = {k: x for k, x in v.items() if not k.startswith("_")}
    (Path(dossier) / "video.json").write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n")


def verifier(v):
    c = config.compte(v["compte"])
    niveau = v.setdefault("niveau", c["theme_detail"].get("niveau", "tout-public"))
    if niveau not in config.NIVEAUX:
        raise SystemExit(f"Niveau « {niveau} » inconnu ({', '.join(config.NIVEAUX)}).")
    if not config.niveau_ok(niveau, config.niveau_max_compte(c)):
        raise SystemExit(f"Vidéo « {niveau} » refusée : le compte {v['compte']} est réglé sur nsfw: {c.get('nsfw', 'non')}.")
    if not config.reseaux_autorises(v["compte"], niveau):
        raise SystemExit(f"Aucun réseau du compte {v['compte']} n'accepte le niveau {niveau}.")
    for i, p in enumerate(v["plans"]):
        if p.get("type") not in ("titre", "photo", "illustration", "fiche", "compteur", "video"):
            raise SystemExit(f"Plan {i + 1} : type « {p.get('type')} » inconnu.")
        if "a" not in p:
            raise SystemExit(f"Plan {i + 1} : il manque « a » (les mots du script où le plan commence).")
    return c


def resoudre_plans(v, mots, duree):
    """Place chaque plan sur la voix à partir des mots où il commence."""
    pos, plans = 0, []
    for i, p in enumerate(v["plans"]):
        idx = voix.trouver(mots, p["a"], pos) if i else 0
        pos = idx
        q = dict(p, _id=i, _idx=idx, _debut=0.0 if i == 0 else mots[idx]["s"])
        if p.get("tampon"):
            frag = p["tampon"].get("a", p["tampon"]["texte"])
            try: j = voix.trouver(mots, frag, idx)
            except ValueError: j = voix.trouver(mots, frag, 0) if i else idx   # mot placé un plan trop tôt
            q["_tampon_t"] = mots[j]["s"]
        plans.append(q)
    for a, b in zip(plans, plans[1:]): a["_fin"] = b["_debut"]
    plans[-1]["_fin"] = duree
    return plans


def visuels(p):
    """Les visuels d'un plan : liste « visuels », ou l'ancien format (fichier / prompt / recherche)."""
    if p.get("visuels"): return p["visuels"]
    v = {}
    if p.get("fichier"): v["photo"] = p["fichier"]
    if p.get("recherche"): v["recherche"] = p["recherche"]
    if p.get("prompt"): v["prompt"] = p["prompt"]
    return [v] if v else []


SEUIL_PERTINENCE = 0.235


MAUVAIS = ["wax", "tussaud", "calligram", "statue", "stamp", "timbre", "signature", "logo", "coat_of_arms", "blason",
           "map", "carte", "autograph", "poster", "affiche", "caricature", "cartoon"]


def _plat(x):
    import unicodedata
    return unicodedata.normalize("NFD", x.lower()).encode("ascii", "ignore").decode().replace(" ", "_")


def ajuster(nom, recherche, score):
    """CLIP ne reconnaît pas les visages : le nom de la personne dans le fichier compte, les faux portraits non."""
    n = _plat(nom)
    noms_propres = [_plat(m) for m in recherche.split() if m[:1].isupper() and len(m) > 2]
    if noms_propres and all(m in n for m in noms_propres): score += 0.05
    elif noms_propres and any(m in n for m in noms_propres): score += 0.025
    if any(m in n for m in MAUVAIS): score -= 0.08
    return score


def choisir_photo(vis, cache, deja, n=4):
    """Télécharge quelques photos candidates et garde celle que CLIP juge la plus proche du plan (ou aucune)."""
    noms = images.chercher_photos(vis["recherche"], n * 2)[:n]     # la même photo peut revenir (ex. le même suspect)
    cands = [(nom, images.photo_commons(nom, cache)) for nom in noms]
    cands = [(nom, f) for nom, f in cands if f]
    if not cands: return None, None
    try:
        from . import pertinence
        texte = vis.get("decrit") or vis["recherche"]
        sc = pertinence.scores([f for _, f in cands], [texte])[:, 0]
        sc = [ajuster(nom, vis["recherche"], x) for (nom, _), x in zip(cands, sc)]
        import numpy as np; sc = np.array(sc)
        i = int(sc.argmax())
        print(f"  photos pour « {texte} » : " + ", ".join(f"{n[:30]} {x:.2f}" for (n, _), x in zip(cands, sc)), flush=True)
        if sc[i] < SEUIL_PERTINENCE:
            print("  aucune assez pertinente, illustration à la place", flush=True); return None, None
        return cands[i][1], cands[i][0]
    except Exception as e:
        print("  analyse d'image impossible, première photo gardée :", e, flush=True)
        return cands[0][1], cands[0][0]


def preparer_images(v, theme, dossier):
    """Photos tout de suite ; illustrations demandées en arrière-plan (1 toutes les 45 s, limite gratuite),
    et traitées (netteté, profondeur) au fil de leur arrivée : l'attente sert à travailler sur le reste."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    cache = Path(dossier) / "cache"; cache.mkdir(exist_ok=True)
    style = theme["style_visuel"]; teinte = style.get("grade", "sepia")
    assets, sources, fichiers, deja = {}, {}, {}, set()
    prets, attente = {}, {}                  # (plan, k) -> (fichier, générée, crédit) ; futur -> (plan, k, vis)
    file = ThreadPoolExecutor(max_workers=1)
    for p in v["_plans"]:
        for k, vis in enumerate(visuels(p)):
            fichier, credit = None, None
            if vis.get("photo"):
                fichier = images.photo_commons(vis["photo"], cache)
                if fichier: credit = f"Wikimedia Commons : {vis['photo']}"; deja.add(vis["photo"])
            if fichier is None and vis.get("recherche"):
                fichier, nom = choisir_photo(vis, cache, deja)
                if fichier: credit = f"Wikimedia Commons : {nom}"; deja.add(nom)
            if fichier:
                prets[(p["_id"], k)] = (fichier, False, credit, vis)
            elif vis.get("prompt"):
                f = file.submit(images.illustration, vis["prompt"], style["prompt"], cache, vis.get("graine", p.get("graine", 1)))
                attente[f] = (p["_id"], k, vis)

    def traiter(pid, k, fichier, generee, credit, vis):
        cle = f"{pid}.{k}"
        img, dep = images.preparer(fichier, teinte, generee, vis.get("recadrage"))
        assets[cle] = (img, dep, *images.point_fort(dep))
        sources[cle] = credit; fichiers.setdefault(pid, fichier)

    for (pid, k), (fichier, generee, credit, vis) in prets.items():   # pendant que les illustrations arrivent
        traiter(pid, k, fichier, generee, credit, vis)
    for f in as_completed(attente):
        pid, k, vis = attente[f]
        fichier = f.result()
        if fichier: traiter(pid, k, fichier, True, "Illustration générée (Pollinations)", vis)
    file.shutdown()
    for p in v["_plans"]:
        p["_cles"] = sorted((c for c in assets if c.split(".")[0] == str(p["_id"])), key=lambda c: int(c.split(".")[1]))
    return assets, sources, fichiers


CAMS = ["avance", "droite", "recule", "gauche", "monte"]


def decouper(plans, densite=2.2):
    """Chaque plan devient des sous-plans d'environ `densite` secondes : visuels différents, puis gros plans
    sur le sujet quand un visuel revient. Les plans de texte reçoivent un fond (le dernier visuel, flouté)."""
    dernier = None
    tous = [c for p in plans for c in p.get("_cles", [])]
    for i, p in enumerate(plans):
        cles = p.get("_cles", [])
        if p["type"] in ("titre", "fiche", "compteur"):
            p["_fond"] = cles[0] if cles else (dernier or (tous[0] if tous else None))
            p["_sous"] = []
            continue
        if not cles:
            p["_sous"] = []; continue
        d = p["_fin"] - p["_debut"]
        n = max(len(cles), min(int(round(d / densite)), int(d // 1.2) or 1))
        pas = d / n
        p["_sous"] = []
        for j in range(n):
            cle = cles[j % len(cles)]
            detail = j >= len(cles) and (j // len(cles)) % 2 == 1
            p["_sous"].append({"debut": p["_debut"] + j * pas, "fin": p["_debut"] + (j + 1) * pas, "cle": cle,
                               "camera": p.get("camera", CAMS[(i + j) % len(CAMS)]) if j == 0 else CAMS[(i + j) % len(CAMS)],
                               "zoom": 1.55 if detail else 1.0, "focus": p.get("focus", 0.5)})
        dernier = cles[-1]
    return plans


def faire_miniature(v, dossier, fichiers, th):
    """Miniature : les plans choisis dans « miniature.plans » (numéros à partir de 1), sinon les deux premiers illustrés."""
    m = v.get("miniature", {})
    choix = [i - 1 for i in m.get("plans", [])] or sorted(fichiers)[:2]
    imgs = [fichiers[i] for i in choix if i in fichiers][:2]
    miniature.fabriquer(dossier / "miniature.jpg", *(imgs + [None, None])[:2], m.get("titre", v["titre"]),
                        m.get("tampon"), th["style_visuel"]["couleurs"])


def fabriquer(dossier, planche_seule=False):
    dossier = Path(dossier); v = lire(dossier); c = verifier(v); th = c["theme_detail"]
    t0 = time.time()
    script = v["script"].strip()
    empreinte = hashlib.md5(f"{script}{c['voix']}".encode()).hexdigest()[:10]
    wav, calage_f = dossier / "voix.wav", dossier / "mots.json"
    if not wav.exists() or not calage_f.exists() or json.loads(calage_f.read_text()).get("empreinte") != empreinte:
        for essai in range(3):     # la voix peut dérailler sur une phrase : on la refait avec un autre tirage
            os.environ["SQUABOT_VOX_GRAINE"] = str(100 * essai)
            print("Voix…" + (f" (essai {essai + 1})" if essai else ""), flush=True)
            _, utilisee = voix.synthese_auto(script, wav, c["voix"], c.get("langue", "fr"), c.get("registre", "jeune"), c.get("accent"))
            v["voix_utilisee"] = utilisee
            print("Calage mot à mot…", flush=True)
            mots = voix.calage(wav, script, langue=c.get("langue", "fr"))
            if not voix.mal_dit(mots): break
            print("  voix mal prononcée par endroits", flush=True)
        else:
            v["alerte"] = "voix mal prononcée par endroits : à écouter avant de poster"
        calage_f.write_text(json.dumps({"empreinte": empreinte, "mots": mots}, ensure_ascii=False))
    mots = json.loads(calage_f.read_text())["mots"]
    import soundfile as sf
    duree = round(sf.info(str(wav)).duration + 0.4, 2)
    v["_plans"] = resoudre_plans(v, mots, duree)
    print("Images…", flush=True)
    assets, sources, fichiers = preparer_images(v, th, dossier)
    decouper(v["_plans"], th.get("densite", 2.2))
    r = Rendu(v, mots, assets, th, duree)
    r.planche(dossier / "planche.jpg")
    if planche_seule: return
    print("Son…", flush=True)
    dernier = v["_plans"][-1]["_debut"]
    fichier_musique, credit_musique = son.choisir_musique(th.get("musique", "enquete"), v["id"])
    son.mixer(wav, dossier / "mix.wav", duree, r.impacts, "nappe-sombre", dernier, fichier_musique)
    print("Rendu…", flush=True)
    sortie = dossier / "video.mp4"
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", str(dossier / "mix.wav"), "-c:v", "libx264", "-preset", "medium",
                          "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                          "-movflags", "+faststart", str(sortie)], stdin=subprocess.PIPE)
    n = int(duree * FPS)
    for i in range(n):
        p.stdin.write(r.image(i / FPS).tobytes())
        if i % 300 == 0: print(f"  {i}/{n}", flush=True)
    p.stdin.close(); p.wait()
    faire_miniature(v, dossier, fichiers, th)
    depot = os.environ.get("SQUABOT_DEPOT_DONNEES") or os.environ.get("GITHUB_REPOSITORY")
    if depot:                                    # la vidéo est rangée dans une release du dépôt des données
        v["video_url"] = f"https://github.com/{depot}/releases/download/{v['id']}/video.mp4"
    v["duree"] = duree
    v["credits_images"] = sorted(set(x for x in sources.values() if x))
    v["credit_musique"] = credit_musique
    v["statut"] = "a_valider"
    v["fabriquee_le"] = time.strftime("%Y-%m-%d %H:%M")
    ecrire(dossier, v)
    print(f"Terminé en {time.time() - t0:.0f} s : {sortie}", flush=True)
