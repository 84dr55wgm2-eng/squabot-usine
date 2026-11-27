"""Risque « contenu produit en masse » : mesure à quel point les vidéos d'une chaîne se ressemblent.

YouTube examine une chaîne dans son ensemble (thème, vidéos récentes, plus vues) et retire la monétisation quand
elles semblent sorties d'un même moule. Aucun algorithme ne garantit l'acceptation, mais la ressemblance se mesure :
même texte, même forme, même accroche, même suite de plans, même modèle de titre. On la mesure ici et on bloque
avant qu'une vidéo trop proche ne soit fabriquée.

Score de risque de 0 (très varié) à 100 (moule unique). Repères : < 35 sain, 35-60 à surveiller, > 60 danger."""
import itertools, json, math, re, unicodedata
from collections import Counter
from . import config

ACCROCHES = {
    "question": re.compile(r"\?\s*$"),
    "chiffre": re.compile(r"^\D{0,25}\d|^(un|deux|trois|quatre|cinq|dix|cent|mille|million)\b", re.I),
    "citation": re.compile(r"^[«\"“]"),
    "defi": re.compile(r"^(essaie|imagine|devine|regarde|try|imagine|guess)", re.I),
    "affirmation_choc": re.compile(r"\b(jamais|personne|aucun|impossible|interdit|secret|never|nobody|nadie|nunca)\b", re.I),
}


def _norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def accroche(script):
    l = next((x.strip() for x in (script or "").split("\n") if x.strip()), "")
    for nom, rx in ACCROCHES.items():
        if rx.search(l): return nom
    return "scene"


def squelette_titre(titre):
    """« Le jour où la Joconde a disparu » -> « le jour ou X a X » : le modèle du titre sans son sujet."""
    m = re.findall(r"[a-z0-9']+", _norm(titre))
    outils = set("le la les l un une des de du d et a au aux en pour par sur dans avec qui que quoi ou comment pourquoi quand "
                 "jour fois secret verite vraie histoire est sont a ont ce cette ces il elle on personne jamais".split())
    return " ".join(x if x in outils or x.isdigit() and len(x) < 2 else "X" for x in m)[:60]


def _ngrammes(t, n=4):
    t = re.sub(r"\s+", " ", _norm(t))
    return Counter(t[i:i + n] for i in range(max(0, len(t) - n + 1)))


def cosinus(a, b):
    if not a or not b: return 0.0
    num = sum(v * b.get(k, 0) for k, v in a.items())
    return num / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


def _sans_sujet(script, titre, mots_cles):
    """Retire les mots propres au sujet : on compare la façon de raconter, pas le sujet."""
    propres = {_norm(x) for x in re.findall(r"\w+", (titre or "") + " " + " ".join(mots_cles or [])) if len(x) > 3}
    return " ".join(w for w in re.findall(r"\w+", _norm(script)) if w not in propres)


def plans_suite(v):
    return [p.get("type", "?") for p in v.get("plans", [])]


def suite_similaire(a, b):
    """Ressemblance de deux suites de plans (0-1), par plus longue sous-suite commune."""
    if not a or not b: return 0.0
    m = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            m[i + 1][j + 1] = m[i][j] + 1 if x == y else max(m[i][j + 1], m[i + 1][j])
    return m[-1][-1] / max(len(a), len(b))


def profil(v):
    s = v.get("script", "")
    return {"format": v.get("forme") or "?", "accroche": accroche(s), "titre": squelette_titre(v.get("titre", "")),
            "texte": _ngrammes(_sans_sujet(s, v.get("titre"), v.get("mots_cles"))), "plans": plans_suite(v),
            "musique": v.get("credit_musique"), "debut": " ".join(re.findall(r"\w+", _norm(s))[:3])}


def _entropie(valeurs):
    c = Counter(valeurs); n = sum(c.values())
    if n <= 1: return 1.0
    h = -sum(k / n * math.log(k / n) for k in c.values())
    return h / math.log(min(n, max(2, len(c)))) if len(c) > 1 else 0.0


def risque(videos):
    """videos : les dernières vidéos d'une chaîne (anciennes -> récentes). Renvoie (score, détails)."""
    P = [profil(v) for v in videos[-20:]]
    if len(P) < 3: return 0, {"note": "trop peu de vidéos pour juger"}
    paires = list(itertools.combinations(P, 2))
    texte = sum(cosinus(a["texte"], b["texte"]) for a, b in paires) / len(paires)
    plans = sum(suite_similaire(a["plans"], b["plans"]) for a, b in paires) / len(paires)
    titres = 1 - len({p["titre"] for p in P}) / len(P)
    formes = 1 - _entropie([p["format"] for p in P])
    accr = 1 - _entropie([p["accroche"] for p in P])
    debuts = 1 - len({p["debut"] for p in P}) / len(P)
    # le texte d'histoires différentes se ressemble naturellement un peu (~0,55 en 4-grammes) : on compte l'excédent
    texte_ex = max(0.0, (texte - 0.55) / 0.35)
    d = {"texte": texte_ex, "suite_de_plans": max(0.0, (plans - 0.45) / 0.45), "modele_de_titre": titres,
         "forme": formes, "accroche": accr, "debut": debuts}
    poids = {"texte": 25, "suite_de_plans": 20, "modele_de_titre": 15, "forme": 15, "accroche": 15, "debut": 10}
    score = round(sum(poids[k] * min(1.0, v) for k, v in d.items()))
    return score, {k: round(v, 2) for k, v in d.items()}


def comparer(v, autres):
    """Une nouvelle vidéo contre les 10 dernières de la chaîne : (bloquants, conseils)."""
    bloq, cons = [], []
    autres = list(autres)[-10:]
    if not autres: return bloq, cons
    p = profil(v); A = [profil(o) for o in autres]
    for o, a in zip(autres, A):
        sim = cosinus(p["texte"], a["texte"])
        if sim > 0.9: bloq.append(f"texte presque identique à « {o.get('titre', '?')} » ({sim:.0%})"); break
    if p["format"] == "?": cons.append("indique la « forme » (récit, liste, enquête… voir strategie.yaml)")
    elif len(A) >= 2 and A[-1]["format"] == A[-2]["format"] == p["format"]:
        bloq.append(f"3e vidéo de suite en forme « {p['format']} » : change de forme")
    elif A[-1]["format"] == p["format"]: cons.append(f"même forme que la vidéo précédente ({p['format']})")
    if len(A) >= 2 and A[-1]["accroche"] == A[-2]["accroche"] == p["accroche"]:
        cons.append(f"3e accroche de suite du type « {p['accroche']} » : varier")
    if sum(1 for a in A if a["titre"] == p["titre"]) >= 2:
        bloq.append(f"modèle de titre déjà utilisé 2 fois récemment (« {p['titre']} »)")
    proches = [o.get("titre", "?") for o, a in zip(autres, A) if suite_similaire(p["plans"], a["plans"]) > 0.9 and len(p["plans"]) > 5]
    if len(proches) >= 2: cons.append(f"même suite de plans que {len(proches)} vidéos récentes : réorganise les plans")
    return bloq, cons


def par_chaine():
    racine = config.RACINE / "data" / "videos"
    vids = sorted(((f.parent.name, json.loads(f.read_text())) for f in racine.glob("*/video.json")), key=lambda x: x[0]) if racine.exists() else []
    out = {}
    for cid in config.comptes():
        vs = [v for _, v in vids if v.get("compte") == cid and v.get("statut") not in ("rejete",)]
        out[cid] = risque(vs) + (len(vs),)
    return out
