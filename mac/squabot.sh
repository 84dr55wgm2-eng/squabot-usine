#!/bin/bash
# Squabot sur le Mac : préparer (une fois) et relier les chaînes YouTube.
# Lancer depuis le Terminal :
#   curl -fsSL https://raw.githubusercontent.com/84dr55wgm2-eng/squabot-usine/main/mac/squabot.sh -o /tmp/squabot.sh && bash /tmp/squabot.sh
# Rien n'est envoyé ailleurs que chez GitHub et Google. Les clés restent dans le trousseau du Mac et dans les
# secrets chiffrés de GitHub.
set -u
USINE="84dr55wgm2-eng/squabot-usine"
DONNEES_DEPOT="84dr55wgm2-eng/squabot"
DOSSIER="$HOME/Squabot"
VENV="$DOSSIER/.venv"
GH="gh"

titre() { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
attention() { printf '  \033[33m!\033[0m %s\n' "$1"; }
stop() { printf '\n\033[31m✗ %s\033[0m\n' "$1"; exit 1; }
entree() { printf '\n  → %s ' "$1"; read -r _ </dev/tty; }
demander() { local r; printf '  %s : ' "$1" >/dev/tty; read -r r </dev/tty; printf '%s' "$r"; }
demander_cache() { local r; printf '  %s (rien ne s'"'"'affiche, c'"'"'est normal) : ' "$1" >/dev/tty; read -rs r </dev/tty; printf '\n' >/dev/tty; printf '%s' "$r"; }

trousseau_lire() { security find-generic-password -s squabot -a "$1" -w 2>/dev/null; }
trousseau_ecrire() { security add-generic-password -U -s squabot -a "$1" -w "$2" >/dev/null; }
secret_github() { printf '%s' "$2" | "$GH" secret set "$1" --repo "$USINE" >/dev/null || stop "Impossible d'enregistrer le secret $1 sur GitHub."; ok "secret $1 enregistré sur GitHub"; }

# ---------- outils ----------
outils() {
  titre "1. Outils du Mac"
  if ! xcode-select -p >/dev/null 2>&1; then
    attention "macOS va installer ses outils de base (git, python). Accepte la fenêtre, attends la fin, puis relance ce script."
    xcode-select --install 2>/dev/null; exit 0
  fi
  ok "git et python3"
  if command -v gh >/dev/null 2>&1; then GH="gh"
  elif [ -x "$DOSSIER/.gh/bin/gh" ]; then GH="$DOSSIER/.gh/bin/gh"
  elif command -v brew >/dev/null 2>&1; then brew install gh >/dev/null && GH="gh"
  else
    mkdir -p "$DOSSIER/.gh"; local arch="amd64"; [ "$(uname -m)" = "arm64" ] && arch="arm64"
    local url; url=$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest | grep -o "https://[^\"]*macOS_${arch}\.zip" | head -1)
    [ -n "$url" ] || stop "Téléchargement de l'outil GitHub impossible."
    curl -fsSL "$url" -o "$DOSSIER/.gh/gh.zip" && (cd "$DOSSIER/.gh" && unzip -qo gh.zip && rm gh.zip && mv gh_*/* . && rmdir gh_* 2>/dev/null)
    GH="$DOSSIER/.gh/bin/gh"; [ -x "$GH" ] || stop "Installation de l'outil GitHub impossible."
  fi
  ok "outil GitHub ($("$GH" --version | head -1))"
  if ! "$GH" auth status >/dev/null 2>&1; then
    titre "Connexion à GitHub"
    echo "  Une page GitHub va s'ouvrir : copie le code affiché ici, colle-le, valide."
    "$GH" auth login --hostname github.com --git-protocol https --web </dev/tty || stop "Connexion GitHub annulée."
  fi
  "$GH" auth setup-git >/dev/null 2>&1
  ok "connecté à GitHub"
  mkdir -p "$DOSSIER"
  if [ -d "$DOSSIER/usine/.git" ]; then git -C "$DOSSIER/usine" pull -q; else git clone -q "https://github.com/$USINE.git" "$DOSSIER/usine" || stop "Téléchargement du moteur impossible."; fi
  if [ -d "$DOSSIER/donnees/.git" ]; then git -C "$DOSSIER/donnees" pull -q --rebase; else "$GH" repo clone "$DONNEES_DEPOT" "$DOSSIER/donnees" -- -q || stop "Accès au dépôt privé squabot impossible."; fi
  ok "moteur et données dans $DOSSIER"
  if [ ! -x "$VENV/bin/python" ]; then python3 -m venv "$VENV" || stop "Python indisponible."; fi
  "$VENV/bin/pip" install -q --disable-pip-version-check cryptography==50.0.1 PyYAML==6.0.3 || stop "Installation Python impossible."
  ok "python prêt"
}

# ---------- préparation (une fois) ----------
preparer() {
  titre "2. Clé de chiffrement"
  local cle; cle=$(trousseau_lire SQUABOT_CLE)
  if [ -z "$cle" ]; then
    cle=$("$VENV/bin/python" -c "import secrets;print(secrets.token_urlsafe(32))"); trousseau_ecrire SQUABOT_CLE "$cle"
    secret_github SQUABOT_CLE "$cle"
  else ok "déjà faite (trousseau du Mac)"; fi

  titre "3. Clé d'accès aux données (SQUABOT_TOKEN)"
  if [ -z "$(trousseau_lire SQUABOT_TOKEN_FAIT)" ] && "$GH" secret list --repo "$USINE" 2>/dev/null | grep -q '^SQUABOT_TOKEN'; then
    trousseau_ecrire SQUABOT_TOKEN_FAIT oui
  fi
  if [ -z "$(trousseau_lire SQUABOT_TOKEN_FAIT)" ]; then
    echo "  Sur la page qui s'ouvre :"
    echo "    • Token name : squabot      • Expiration : la plus longue proposée"
    echo "    • Repository access : Only select repositories → squabot"
    echo "    • Permissions → Repository permissions → Contents : Read and write"
    echo "    • Generate token, puis copie la clé (elle commence par github_pat_)"
    open "https://github.com/settings/personal-access-tokens/new"
    local pat; pat=$(demander_cache "Colle la clé ici")
    case "$pat" in github_pat_*|ghp_*) ;; *) stop "Ce n'est pas une clé GitHub (elle commence par github_pat_). Relance le script.";; esac
    secret_github SQUABOT_TOKEN "$pat"; trousseau_ecrire SQUABOT_TOKEN_FAIT oui
  else ok "déjà faite"; fi

  titre "4. Projet Google (YouTube)"
  if [ -z "$(trousseau_lire GOOGLE_CLIENT_ID)" ]; then
    echo "  Je t'ouvre les pages une par une. Fais l'étape, puis Entrée ici."
    open "https://console.cloud.google.com/projectcreate"
    entree "Crée le projet « Squabot » (bouton Créer), attends qu'il soit prêt, puis Entrée."
    open "https://console.cloud.google.com/apis/library/youtube.googleapis.com"
    entree "Vérifie en haut que le projet Squabot est choisi, clique « Activer », puis Entrée."
    open "https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com"
    entree "Clique « Activer » (statistiques et revenus), puis Entrée."
    open "https://console.cloud.google.com/auth/overview/create"
    entree "Écran de consentement : nom Squabot, ton e-mail, Audience « Externe », Créer. Puis Entrée."
    open "https://console.cloud.google.com/auth/audience"
    entree "Clique « Publier l'application » puis Confirmer (sinon l'accès se coupe au bout de 7 jours). Puis Entrée."
    open "https://console.cloud.google.com/auth/clients/create"
    echo "  Type d'application : « Application de bureau », nom Squabot Mac, Créer."
    local id sec
    id=$(demander "Colle l'ID client (finit par .apps.googleusercontent.com)")
    case "$id" in *.apps.googleusercontent.com) ;; *) stop "Ce n'est pas un ID client Google. Relance le script.";; esac
    sec=$(demander_cache "Colle le code secret du client")
    [ -n "$sec" ] || stop "Code secret vide."
    trousseau_ecrire GOOGLE_CLIENT_ID "$id"; trousseau_ecrire GOOGLE_CLIENT_SECRET "$sec"
    secret_github GOOGLE_CLIENT_ID "$id"; secret_github GOOGLE_CLIENT_SECRET "$sec"
  else ok "déjà fait"; fi

  titre "5. Essai de l'usine"
  "$GH" workflow run tendances.yml --repo "$USINE" >/dev/null 2>&1 && ok "relevé des tendances lancé : il s'enregistrera dans tes données d'ici 2 minutes" || attention "lancement impossible pour l'instant, ce n'est pas bloquant"
}

# ---------- relier une chaîne ----------
relier() {
  titre "Relier une chaîne YouTube"
  git -C "$DOSSIER/donnees" pull -q --rebase
  local liste; liste=$(cd "$DOSSIER/donnees/comptes" 2>/dev/null && ls *.yaml 2>/dev/null | sed 's/\.yaml$//')
  if [ -z "$liste" ]; then
    attention "Aucune chaîne dans Squabot pour l'instant : crée-la dans l'appli, demande à Claude de synchroniser, puis relance."
    return
  fi
  local i=0 noms=""
  for c in $liste; do
    i=$((i + 1)); local nom; nom=$(grep -m1 '^nom:' "$DOSSIER/donnees/comptes/$c.yaml" | sed 's/^nom: *//')
    local deja=""; [ -f "$DOSSIER/donnees/data/connexions/youtube-$c.chiffre" ] && deja="  (déjà reliée)"
    printf '   %d. %s  [%s]%s\n' "$i" "$nom" "$c" "$deja"; noms="$noms $c"
  done
  local n; n=$(demander "Numéro de la chaîne")
  local compte; compte=$(echo $noms | tr ' ' '\n' | sed -n "${n}p")
  [ -n "$compte" ] || stop "Numéro inconnu."
  echo "  Vérifie d'abord que la chaîne existe sur YouTube (sinon crée-la : youtube.com/channel_switcher)."
  ( cd "$DOSSIER/usine" && SQUABOT_DONNEES="$DOSSIER/donnees" SQUABOT_CLE="$(trousseau_lire SQUABOT_CLE)" \
      GOOGLE_CLIENT_ID="$(trousseau_lire GOOGLE_CLIENT_ID)" GOOGLE_CLIENT_SECRET="$(trousseau_lire GOOGLE_CLIENT_SECRET)" \
      "$VENV/bin/python" -m squabot connecter youtube "$compte" ) || stop "Liaison interrompue."
  ( cd "$DOSSIER/donnees" && git add data/connexions && git commit -qm "Chaîne YouTube reliée : $compte [skip ci]" && \
    for k in 1 2 3; do git pull -q --rebase && git push -q && break; sleep 3; done ) || stop "Envoi vers GitHub impossible."
  ok "c'est enregistré : Squabot pourra publier sur cette chaîne"
}

clear
printf '\033[1mSquabot\033[0m — relier tes chaînes YouTube\n'
outils
if [ -z "$(trousseau_lire GOOGLE_CLIENT_ID)" ] || [ -z "$(trousseau_lire SQUABOT_CLE)" ] || [ -z "$(trousseau_lire SQUABOT_TOKEN_FAIT)" ]; then preparer; fi
while true; do
  relier
  r=$(demander "Relier une autre chaîne ? (o/n)")
  case "$r" in o|O|oui) ;; *) break;; esac
done
titre "Terminé. Tu peux fermer le Terminal."
