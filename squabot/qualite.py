"""Contrôle qualité d'une vidéo écrite, avant fabrication : règles de strategie.yaml (durée, accroche, rythme,
titre, sources, variété). Bloquant = la vidéo ne part pas ; conseil = signalé à Claude."""
import json, re
from pathlib import Path
import yaml
from . import config

STRATEGIE = yaml.safe_load((Path(__file__).parent / "strategie.yaml").read_text())
MOTS_SECONDE = 2.6
SALUTS = re.compile(r"^(salut|bonjour|hello|hey|coucou|aujourd'hui on|dans cette vid)", re.I)
APPELS = re.compile(r"abonne[- ]toi|abonnez[- ]vous|mets? un like|laisse un like|pouce bleu|leave a like|subscribe|suscr[ií]bete|dale like", re.I)


def _debut(script, n=3):
    return " ".join(re.findall(r"\w+", script.lower())[:n])


def controler(v, autres=()):
    """Renvoie (bloquants, conseils) pour une vidéo et les autres vidéos du même compte."""
    bloq, cons = [], []
    script = (v.get("script") or "").strip()
    lignes = [l.strip() for l in script.split("\n") if l.strip()]
    n = len(script.split())
    c = config.comptes().get(v.get("compte"), {})
    fmt = STRATEGIE["durees"]["short"]
    if v.get("format", "short") == "short":
        lo, hi = fmt["mots"]
        if "tiktok" not in c.get("publier_sur", {}): lo = 110
        if n < lo: bloq.append(f"script trop court : {n} mots (minimum {lo}, soit ~{lo / MOTS_SECONDE:.0f} s)")
        if n > hi + 25: bloq.append(f"script trop long : {n} mots (maximum {hi})")
        elif n > hi: cons.append(f"script un peu long : {n} mots (cible {fmt['mots'][0]}-{hi})")
    if lignes:
        premiere = lignes[0]
        if len(premiere.split()) > 12: cons.append(f"accroche trop longue ({len(premiere.split())} mots, 12 max) : « {premiere[:60]} »")
        if SALUTS.match(premiere): bloq.append("l'accroche commence par une salutation ou une introduction")
    if APPELS.search(script): bloq.append("appel à s'abonner ou liker dans le script (interdit : ça fait fuir)")
    titre = v.get("titre", "")
    if not titre: bloq.append("titre manquant")
    elif len(titre) > STRATEGIE["titre_miniature"]["titre_max_car"]: cons.append(f"titre trop long ({len(titre)} car.)")
    if v.get("verite") == "verifiee" and len(v.get("sources") or []) < 2: bloq.append("sujet vérifié avec moins de 2 sources")
    if not v.get("description"): cons.append("description manquante")
    # rythme : un plan ne doit pas rester plus de ~5 s
    mots = script.split(); pos = []
    texte = " ".join(mots).lower()
    for p in v.get("plans", []):
        i = texte.find(str(p.get("a", "")).lower())
        if i >= 0: pos.append(len(texte[:i].split()))
    pos = sorted(set(pos)) + [n]
    for a, b in zip(pos, pos[1:]):
        if (b - a) / MOTS_SECONDE > 6: cons.append(f"plan de ~{(b - a) / MOTS_SECONDE:.0f} s vers « {' '.join(mots[a:a + 4])} » : couper en deux"); break
    # variété (politique contenu inauthentique) : voir variete.py
    from .variete import comparer
    b2, c2 = comparer(v, autres); bloq += b2; cons += c2
    debut = _debut(script)
    for o in list(autres)[-10:]:
        if debut and _debut(o.get("script") or "") == debut: cons.append(f"même début d'accroche que « {o.get('titre', '?')} » : varier"); break
    if v.get("forme") and v["forme"] not in STRATEGIE["formats"]: cons.append(f"forme « {v['forme']} » inconnue")
    for o in autres:
        if o.get("titre", "").strip().lower() == titre.strip().lower(): bloq.append(f"titre identique à une vidéo existante"); break
    return bloq, cons


def tout_controler():
    """Toutes les vidéos à fabriquer. Renvoie la liste des problèmes bloquants (texte)."""
    racine = config.RACINE / "data" / "videos"
    vids = sorted(((json.loads(f.read_text()), f.parent.name) for f in racine.glob("*/video.json")), key=lambda x: x[1]) if racine.exists() else []
    problemes = []
    for i, (v, d) in enumerate(vids):
        if v.get("statut") != "a_fabriquer": continue
        autres = [o for o, od in vids[:i] if o.get("compte") == v.get("compte")]
        bloq, cons = controler(v, autres)
        for b in bloq: problemes.append(f"{d} : {b}")
        for c in cons: print(f"conseil — {d} : {c}")
    return problemes
