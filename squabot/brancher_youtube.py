"""Brancher une chaîne YouTube depuis le téléphone (connexion Google « par code », comme une télé).

Étape 1 (`debut`) : demande un code à Google et l'affiche dans le résumé du lancement GitHub.
Étape 2 (`attendre`) : attend que tu aies entré le code sur google.com/device et choisi la chaîne,
puis range l'autorisation chiffrée (squabot/coffre.py) et note quelle chaîne a été branchée.

Secrets GitHub nécessaires : GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (identifiant OAuth de type
« TV et périphériques à saisie limitée »), SQUABOT_CLE (phrase de chiffrement).
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from . import coffre, config

PORTEES = ["https://www.googleapis.com/auth/youtube",                     # publier, commentaires
           "https://www.googleapis.com/auth/yt-analytics.readonly",       # vues, rétention
           "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"]  # revenus


def _post(url, champs):
    req = urllib.request.Request(url, urllib.parse.urlencode(champs).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


DEPOT = "https://github.com/84dr55wgm2-eng/squabot-usine"


def _verifier_secrets():
    """Liste ce qui manque, avec les liens directs, dans le résumé visible sur le téléphone."""
    manque = [n for n in ("SQUABOT_CLE", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET") if len(os.environ.get(n, "")) < (16 if n == "SQUABOT_CLE" else 1)]
    if not manque: return
    _resume("## Il manque la préparation (une seule fois)\n\n"
            + "".join(f"- ❌ secret **{n}**\n" for n in manque)
            + f"\n1. Ajoute les secrets ici : {DEPOT}/settings/secrets/actions/new\n"
            "   - `SQUABOT_CLE` : une longue phrase inventée (16 caractères minimum)\n"
            "   - `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET` : l'identifiant OAuth du projet Google "
            "(type « TV et périphériques à saisie limitée »), créé sur https://console.cloud.google.com/apis/credentials\n"
            f"2. Puis relance (bouton **Re-run**).\n\nPas à pas complet : {DEPOT}/blob/main/docs/connexions.md")
    raise SystemExit("Préparation incomplète : " + ", ".join(manque) + " (détails dans le résumé du lancement).")


def _client():
    _verifier_secrets()
    return os.environ["GOOGLE_CLIENT_ID"], os.environ["GOOGLE_CLIENT_SECRET"]


def _resume(texte):
    f = os.environ.get("GITHUB_STEP_SUMMARY")
    if f:
        with open(f, "a") as s: s.write(texte + "\n")
    print(texte, flush=True)


def debut(compte):
    if compte not in config.comptes(): raise SystemExit(f"Compte inconnu : {compte}. Comptes : {', '.join(config.comptes())}")
    cid, _ = _client()
    r = _post("https://oauth2.googleapis.com/device/code", {"client_id": cid, "scope": " ".join(PORTEES)})
    if r.get("error") == "invalid_scope":           # Google refuse les statistiques par code : on garde l'essentiel
        r = _post("https://oauth2.googleapis.com/device/code", {"client_id": cid, "scope": PORTEES[0]})
    if "user_code" not in r: raise SystemExit(f"Google refuse la demande : {r}")
    nom = config.comptes()[compte]["nom"]
    _resume(f"## Brancher « {nom} » à YouTube\n\n"
            f"1. Ouvre **{r['verification_url']}** sur ton téléphone\n"
            f"2. Entre le code **`{r['user_code']}`**\n"
            f"3. Choisis la chaîne **{nom}** et autorise Squabot\n\n"
            f"Le code expire dans {r['expires_in'] // 60} minutes. Cette page se met à jour toute seule une fois fini.")
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as o:
        o.write(f"device_code={r['device_code']}\nintervalle={r.get('interval', 5)}\nexpire={r['expires_in']}\n")


def attendre(compte, device_code, intervalle=5, expire=1800):
    cid, sec = _client()
    fin = time.time() + int(expire)
    intervalle = int(intervalle)
    while time.time() < fin:
        time.sleep(intervalle)
        r = _post("https://oauth2.googleapis.com/token", {"client_id": cid, "client_secret": sec, "device_code": device_code,
                                                         "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        if r.get("error") == "authorization_pending": continue
        if r.get("error") == "slow_down": intervalle += 5; continue
        if r.get("error"): raise SystemExit(f"Branchement annulé : {r.get('error')} {r.get('error_description', '')}")
        if "refresh_token" not in r: raise SystemExit("Google n'a pas donné d'autorisation durable : relance le branchement.")
        sn = enregistrer(compte, r)
        _resume(f"### Branché ✅\n\nChaîne **{sn.get('title', '?')}** ({sn.get('customUrl', '')}) reliée au compte `{compte}`.")
        return
    raise SystemExit("Le code a expiré sans être utilisé : relance le branchement.")


def enregistrer(compte, r):
    """Range l'autorisation Google (réponse du jeton) chiffrée dans le coffre et note la chaîne reliée. Renvoie son snippet."""
    req = urllib.request.Request("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                                 headers={"Authorization": f"Bearer {r['access_token']}"})
    items = json.load(urllib.request.urlopen(req, timeout=30)).get("items", [])
    chaine = items[0] if items else {}
    sn = chaine.get("snippet", {})
    coffre.ranger("youtube", compte, {"refresh_token": r["refresh_token"], "portees": r.get("scope", ""),
                                      "chaine_id": chaine.get("id")})
    etat_f = coffre.DOSSIER / "etat.json"
    etat = json.loads(etat_f.read_text()) if etat_f.exists() else {}
    etat.setdefault(compte, {})["youtube"] = {"chaine": sn.get("title"), "identifiant": sn.get("customUrl"),
                                              "chaine_id": chaine.get("id"), "branche_le": time.strftime("%Y-%m-%d %H:%M"),
                                              "statistiques": "yt-analytics" in r.get("scope", "")}
    etat_f.write_text(json.dumps(etat, ensure_ascii=False, indent=1))
    return sn


if __name__ == "__main__":
    {"debut": debut, "attendre": attendre}[sys.argv[1]](*sys.argv[2:])
