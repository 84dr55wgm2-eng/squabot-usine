"""Brancher un compte d'un réseau, une seule fois, depuis ton ordinateur (Mac).

    python -m squabot connecter youtube histoire-fr      connexion Google officielle (API YouTube)
    python -m squabot connecter tiktok histoire-fr       navigateur : tu te connectes, la session est gardée
    python -m squabot connecter instagram histoire-fr    idem (ou API officielle Meta, voir docs/connexions.md)
    python -m squabot connecter facebook histoire-fr
    python -m squabot connecter x recits-adultes-x

La connexion est rangée chiffrée dans les secrets du dépôt GitHub (outil « gh », connecté une fois par
« gh auth login »), sous le nom RESEAU_COMPTE, par exemple YOUTUBE_HISTOIRE_FR. Elle n'est jamais écrite dans le dépôt.
"""
import base64, http.server, json, secrets, subprocess, sys, threading, urllib.parse, urllib.request, webbrowser
from pathlib import Path
from . import config

DEPOT = "84dr55wgm2-eng/squabot"
PAGES = {"tiktok": "https://www.tiktok.com/login", "instagram": "https://www.instagram.com/accounts/login/",
         "facebook": "https://www.facebook.com/login", "x": "https://x.com/i/flow/login"}
PORTEES_YOUTUBE = ["https://www.googleapis.com/auth/youtube.upload",        # publier
                   "https://www.googleapis.com/auth/youtube.force-ssl",     # lire et répondre aux commentaires
                   "https://www.googleapis.com/auth/yt-analytics.readonly", # vues et rétention
                   "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"]  # revenus


def nom_secret(reseau, compte):
    return f"{reseau}_{compte}".upper().replace("-", "_")


def ranger(nom, valeur):
    subprocess.run(["gh", "secret", "set", nom, "--repo", DEPOT, "--body", valeur], check=True)
    print(f"Connexion rangée dans le secret GitHub {nom}. Le tableau de bord l'affichera au prochain relevé.")


def youtube(compte, client_json="client_secret.json"):
    """OAuth Google « application de bureau » : le navigateur s'ouvre, tu choisis la chaîne, c'est fini."""
    c = json.loads(Path(client_json).read_text())
    c = c.get("installed") or c.get("web")
    code, etat = {}, secrets.token_urlsafe(16)

    class Retour(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == etat: code["v"] = q.get("code", [""])[0]
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write("<h2>C'est connecté. Tu peux fermer cette page.</h2>".encode())
        def log_message(self, *a): pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Retour)
    retour = f"http://127.0.0.1:{srv.server_port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": retour, "response_type": "code", "scope": " ".join(PORTEES_YOUTUBE),
        "access_type": "offline", "prompt": "consent", "state": etat})
    threading.Thread(target=srv.handle_request, daemon=True).start()
    print("Choisis la chaîne du compte", compte, "dans la fenêtre qui s'ouvre…"); webbrowser.open(url)
    while "v" not in code: threading.Event().wait(0.5)
    jetons = json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", urllib.parse.urlencode({
        "code": code["v"], "client_id": c["client_id"], "client_secret": c["client_secret"],
        "redirect_uri": retour, "grant_type": "authorization_code"}).encode()).read())
    if "refresh_token" not in jetons: raise SystemExit("Google n'a pas donné de jeton durable : recommence.")
    ranger(nom_secret("youtube", compte), json.dumps({"client_id": c["client_id"], "client_secret": c["client_secret"],
                                                       "refresh_token": jetons["refresh_token"]}))


def navigateur(reseau, compte):
    """Ouvre un vrai navigateur : tu te connectes normalement (code SMS compris), puis Entrée. La session est gardée."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=False)
        ctx = nav.new_context(locale="fr-FR")
        ctx.new_page().goto(PAGES[reseau])
        input(f"Connecte-toi au compte {reseau} de « {compte} » dans la fenêtre, puis appuie sur Entrée ici… ")
        etat = ctx.storage_state()
        nav.close()
    ranger(nom_secret(reseau, compte), base64.b64encode(json.dumps(etat).encode()).decode())


def main(a):
    if len(a) < 2: raise SystemExit(__doc__)
    reseau, compte = a[0], a[1]
    if compte not in config.comptes(): raise SystemExit(f"Compte inconnu : {compte}")
    if reseau not in (config.comptes()[compte].get("publier_sur") or {}):
        raise SystemExit(f"Le compte {compte} ne publie pas sur {reseau} (voir comptes/{compte}.yaml).")
    if reseau == "youtube": youtube(compte, a[2] if len(a) > 2 else "client_secret.json")
    elif reseau in PAGES: navigateur(reseau, compte)
    else: raise SystemExit(f"Réseau non géré : {reseau}")
