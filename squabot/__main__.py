"""Commandes :
  python -m squabot verifier                  vérifie comptes, thèmes et réseaux
  python -m squabot fabriquer <dossier>       fabrique la vidéo d'un dossier data/videos/<id>
  python -m squabot planche <dossier>         planche-contact seulement (rapide, pour relire)
  python -m squabot a-fabriquer               liste les vidéos en attente de fabrication
  python -m squabot compilations [n]          vidéo longue YouTube dès qu'un compte a n vidéos prêtes (8 par défaut)
  python -m squabot synchroniser <dossier>     crée les comptes demandés dans l'appli (documents exportés)
  python -m squabot connecter <réseau> <compte>   brancher un compte (sur ton Mac, une seule fois)
  python -m squabot tendances [fr en es]      le buzz du moment sur toutes les plateformes (data/tendances/)
  python -m squabot veille                    collecte les sujets frais de chaque thème actif (data/veille/)
  python -m squabot index                     met à jour data/index.json pour le tableau de bord
"""
import json, sys
from pathlib import Path
from . import config

VIDEOS = config.RACINE / "data" / "videos"


def argent(vids):
    """Revenus par compte et réseau : réels quand relevés, sinon estimés (vues × RPM) ; progression vers la monétisation."""
    import datetime as dt
    pf = config.plateformes(); mois = dt.date.today().strftime("%Y-%m")
    out = {"mois": mois, "comptes": {}, "total_reel": 0.0, "total_estime": [0.0, 0.0]}
    for cid, c in config.comptes().items():
        f = config.RACINE / "data" / "stats" / f"{cid}.json"
        st = json.loads(f.read_text()).get("reseaux", {}) if f.exists() else {}
        lignes = {}
        for r in (c.get("publier_sur") or {}):
            s, p = st.get(r, {}), pf.get(r, {})
            reel = (s.get("revenus_reels_eur") or {}).get(mois)
            fmt = "long" if r == "tiktok" else "short"
            rpm = (p.get("rpm_eur") or {}).get(fmt) or [0, 0]
            vues = s.get("vues_30j", 0)
            est = [vues / 1000 * rpm[0], vues / 1000 * rpm[1]]
            prog = {k: min(1.0, (s.get(k, 0) / v) if v else 0) for k, v in (p.get("seuils") or {}).items()}
            lignes[r] = {"reel": reel, "estime": est, "vues_30j": vues, "vues_90j": s.get("vues_90j", 0), "abonnes": s.get("abonnes", 0),
                         "abonnes_certifies": s.get("abonnes_certifies", 0),
                         "seuils": p.get("seuils") or {}, "progression": prog, "connecte": bool(s)}
            if reel: out["total_reel"] += reel
            out["total_estime"][0] += est[0]; out["total_estime"][1] += est[1]
        out["comptes"][cid] = lignes
    return out


def index():
    vids = []
    for f in sorted(VIDEOS.glob("*/video.json")):
        v = json.loads(f.read_text())
        vids.append({k: v.get(k) for k in ("id", "compte", "titre", "statut", "date_prevue", "duree", "niveau",
                                           "verite", "publications", "fabriquee_le", "sources", "miniature_url", "video_url", "description", "titres_possibles")})
        vids[-1]["dossier"] = f.parent.name
        if (f.parent / "miniature.jpg").exists() and not vids[-1].get("miniature_url"):
            vids[-1]["miniature_url"] = f"../data/videos/{f.parent.name}/miniature.jpg"
        if (f.parent / "apercu.mp4").exists():
            vids[-1]["apercu_url"] = f"../data/videos/{f.parent.name}/apercu.mp4"
    import yaml
    idees_f = config.RACINE / "data" / "idees" / "idees.yaml"
    idees = yaml.safe_load(idees_f.read_text()) if idees_f.exists() else []
    cx_f = config.RACINE / "data" / "connexions.json"
    presents = set(json.loads(cx_f.read_text()).get("secrets", [])) if cx_f.exists() else set()
    from .connecter import nom_secret
    from .coffre import branches
    coffre_ok = branches()
    connexions = {cid: {r: nom_secret(r, cid) in presents or r in coffre_ok.get(cid, []) for r in (c.get("publier_sur") or {})}
                  for cid, c in config.comptes().items()}
    data = {"connexions": connexions, "cerveau_actif": "CLAUDE_CODE_OAUTH_TOKEN" in presents, "argent": argent(vids), "idees": idees or [], "comptes": config.comptes(), "themes": config.themes(), "plateformes": config.plateformes(), "videos": vids}
    txt = json.dumps(data, ensure_ascii=False, indent=1)
    (config.RACINE / "data" / "index.json").write_text(txt)
    (config.RACINE / "tableau" / "donnees.js").write_text(f"window.SQUABOT = {txt};\n")
    print(f"{len(vids)} vidéo(s) dans data/index.json")


def compilations(minimum=8):
    """Pour chaque compte ayant assez de vidéos prêtes et pas encore compilées : une vidéo longue YouTube."""
    import datetime as dt, subprocess
    from .compilation import compiler
    for cid, c in config.comptes().items():
        if not c.get("actif"): continue
        prets = []
        for f in sorted(VIDEOS.glob("*/video.json")):
            v = json.loads(f.read_text())
            if v.get("compte") == cid and v.get("statut") in ("a_valider", "valide", "publie") and not v.get("compilee"):
                prets.append((f.parent, v))
        if len(prets) < minimum: print(f"{cid} : {len(prets)}/{minimum} vidéos, pas encore de compilation"); continue
        lot = prets[:12]
        ident = f"{dt.date.today().isoformat()}-compilation-{cid}"
        dossier = config.RACINE / "data" / "compilations" / ident; dossier.mkdir(parents=True, exist_ok=True)
        fichiers = []
        for d, v in lot:
            mp4 = d / "video.mp4"
            if not mp4.exists():
                subprocess.run(["gh", "release", "download", v["id"], "-p", "video.mp4", "-D", str(d)], check=False)
            if mp4.exists(): fichiers.append((v["titre"], mp4))
        if len(fichiers) < minimum: print(f"{cid} : vidéos introuvables"); continue
        th = c["theme_detail"]["nom"]
        titre = f"{len(fichiers)} histoires incroyables · {th}"
        compiler(cid, titre, fichiers, dossier / "video.mp4", dossier / "travail")
        (dossier / "video.json").write_text(json.dumps({"id": ident, "compte": cid, "type": "compilation", "titre": titre,
            "format": "long", "reseaux": ["youtube"], "statut": "a_valider", "contenu": [v["id"] for _, v in lot]},
            ensure_ascii=False, indent=2))
        for d, v in lot:
            v["compilee"] = ident; (d / "video.json").write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n")
        print(f"{cid} : compilation {ident} ({len(fichiers)} histoires)")


def main(a):
    cmd = a[0] if a else "aide"
    if cmd == "verifier":
        pb = config.problemes()
        print("\n".join(pb) if pb else f"OK : {len(config.comptes())} comptes, {len(config.themes())} thèmes.")
        sys.exit(1 if pb else 0)
    elif cmd in ("fabriquer", "planche"):
        from .fabrique import fabriquer
        fabriquer(a[1], planche_seule=cmd == "planche")
    elif cmd == "a-fabriquer":
        for f in sorted(VIDEOS.glob("*/video.json")):
            if json.loads(f.read_text()).get("statut") == "a_fabriquer": print(f.parent)
    elif cmd == "synchroniser":
        from .synchro import synchroniser
        for cid, (st, raison) in synchroniser(a[1]).items(): print(cid, st, raison)
    elif cmd == "connecter":
        from .connecter import main as connecter
        connecter(a[1:])
    elif cmd == "compilations":
        compilations(int(a[1]) if len(a) > 1 else 8)
    elif cmd == "tendances":
        from .tendances import tout as tendances
        tendances(a[1:] or None)
    elif cmd == "veille":
        from .veille import tout_veiller
        tout_veiller()
    elif cmd == "index":
        index()
    else:
        print(__doc__)


main(sys.argv[1:])
