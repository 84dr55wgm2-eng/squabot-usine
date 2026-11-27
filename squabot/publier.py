"""Publication : chaque vidéo « prete » part sur YouTube à son créneau.

Mode `manuel` (tant que Google n'a pas audité le projet : ses envois par l'API restent verrouillés en privé) :
la vidéo est rangée dans data/A-POSTER.md, avec son lien de téléchargement, son titre et sa description à copier.
Mode `auto` (après l'audit) : envoi direct sur la chaîne par l'API YouTube, programmé à `date_prevue`.
Réglage : `publication.mode` dans cerveau.yaml.

    python -m squabot publier
"""
import datetime, json, os, urllib.request, urllib.parse
from zoneinfo import ZoneInfo
import yaml
from . import config, coffre

PARIS = ZoneInfo("Europe/Paris")
VIDEOS = config.RACINE / "data" / "videos"


def reglages():
    f = config.RACINE / "cerveau.yaml"
    c = yaml.safe_load(f.read_text()) if f.exists() else {}
    return (c.get("publication") or {}) | {"mode": (c.get("publication") or {}).get("mode", "manuel")}


def _date(v):
    try: return datetime.datetime.strptime(v.get("date_prevue", "")[:16], "%Y-%m-%d %H:%M").replace(tzinfo=PARIS)
    except ValueError: return None


def _jeton(compte):
    r = coffre.lire("youtube", compte)
    corps = urllib.parse.urlencode({"client_id": os.environ["GOOGLE_CLIENT_ID"], "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                                    "refresh_token": r["refresh_token"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", corps, timeout=30) as rep:
        return json.load(rep)["access_token"]


def envoyer_youtube(v, fichier, quand):
    """Envoi « resumable » de l'API YouTube Data v3. Renvoie l'identifiant de la vidéo."""
    jeton = _jeton(v["compte"])
    maintenant = datetime.datetime.now(PARIS)
    statut = {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    if quand and quand > maintenant + datetime.timedelta(minutes=10):
        statut = {"privacyStatus": "private", "publishAt": quand.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "selfDeclaredMadeForKids": False}
    meta = {"snippet": {"title": v["titre"][:100], "description": v.get("description", "")[:4900],
                        "tags": v.get("tags", [])[:30], "categoryId": "20" if v.get("theme") == "jeux-video" else "24",
                        "defaultLanguage": "fr", "defaultAudioLanguage": "fr"},
            "status": statut}
    taille = os.path.getsize(fichier)
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(meta).encode(), method="POST",
        headers={"Authorization": f"Bearer {jeton}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(taille)})
    with urllib.request.urlopen(req, timeout=60) as rep:
        url = rep.headers["Location"]
    with open(fichier, "rb") as f:
        req = urllib.request.Request(url, data=f.read(), method="PUT",
                                     headers={"Authorization": f"Bearer {jeton}", "Content-Type": "video/mp4"})
    with urllib.request.urlopen(req, timeout=600) as rep:
        vid = json.load(rep)["id"]
    mini = fichier.parent / "miniature.jpg"
    if mini.exists():
        try:
            req = urllib.request.Request(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                                         data=mini.read_bytes(), method="POST",
                                         headers={"Authorization": f"Bearer {jeton}", "Content-Type": "image/jpeg"})
            urllib.request.urlopen(req, timeout=60).read()
        except Exception as e:
            print("  miniature refusée (chaîne non vérifiée par téléphone ?) :", e, flush=True)
    return vid


def a_poster(videos):
    """data/A-POSTER.md : la liste à publier à la main, la plus proche en premier."""
    depot = os.environ.get("SQUABOT_DEPOT_DONNEES", "84dr55wgm2-eng/squabot")
    comptes = config.comptes()
    lignes = ["# À poster", "",
              "Vidéos prêtes, dans l'ordre. Pour chacune : télécharger, publier depuis l'appli YouTube (Short), "
              "coller le titre et la description, puis cocher la case dans `video.json` (`\"statut\": \"publie\"`) "
              "ou laisser le bot la voir en ligne.", ""]
    for d, v in videos:
        nom = (comptes.get(v["compte"]) or {}).get("nom", v["compte"])
        lignes += [f"## {v.get('date_prevue', '?')} · {nom}", "",
                   f"**{v['titre']}**", "",
                   f"- Vidéo : https://github.com/{depot}/releases/download/{v['id']}/video.mp4",
                   f"- Miniature : https://github.com/{depot}/releases/download/{v['id']}/miniature.jpg", "",
                   "Description :", "", "```", v.get("description", ""), "```", ""]
    if not videos: lignes.append("Rien à poster pour l'instant.")
    (config.RACINE / "data" / "A-POSTER.md").write_text("\n".join(lignes) + "\n")


def publier():
    mode = reglages()["mode"]
    maintenant = datetime.datetime.now(PARIS)
    pretes = []
    for f in sorted(VIDEOS.glob("*/video.json")):
        v = json.loads(f.read_text())
        if v.get("statut") not in ("prete", "a_valider"): continue
        if v.get("alerte"): continue
        pretes.append((f.parent, v))
    pretes.sort(key=lambda x: x[1].get("date_prevue", ""))
    if mode != "auto":
        a_poster(pretes)
        print(f"Mode manuel : {len(pretes)} vidéo(s) dans data/A-POSTER.md", flush=True)
        return
    branches = coffre.branches()
    for d, v in pretes:
        quand = _date(v)
        if quand and quand > maintenant + datetime.timedelta(hours=24): continue      # trop tôt
        if "youtube" not in branches.get(v["compte"], []): print(f"{v['id']} : chaîne non reliée", flush=True); continue
        fichier = d / "video.mp4"
        if not fichier.exists():
            depot = os.environ.get("SQUABOT_DEPOT_DONNEES", "84dr55wgm2-eng/squabot")
            os.system(f"gh release download {v['id']} --repo {depot} --pattern video.mp4 --dir {d} --clobber")
        if not fichier.exists(): print(f"{v['id']} : vidéo introuvable", flush=True); continue
        try:
            vid = envoyer_youtube(v, fichier, quand)
        except Exception as e:
            print(f"{v['id']} : envoi refusé : {e}", flush=True); continue
        v.update(statut="envoyee", youtube_id=vid, envoyee_le=maintenant.strftime("%Y-%m-%d %H:%M"))
        (d / "video.json").write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n")
        print(f"{v['id']} → https://youtu.be/{vid}", flush=True)
    a_poster([x for x in pretes if x[1].get("statut") != "envoyee"])
