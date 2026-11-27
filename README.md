# Squabot · usine

Moteur de fabrication de vidéos courtes : voix, calage mot à mot, photos libres et illustrations, effet 2.5D,
transitions, sous-titres, musique, miniature, compilations longues. Tout tourne gratuitement dans GitHub Actions.

Ce dépôt ne contient que le moteur. Les chaînes, sujets, scripts et vidéos vivent dans un dépôt privé séparé,
lu et écrit grâce au secret `SQUABOT_TOKEN`.

| Tâche | Quand |
|---|---|
| Veille du monde | toutes les 6 h |
| Tournée de nuit (Claude) | chaque nuit, si `CLAUDE_CODE_OAUTH_TOKEN` existe |
| Fabrication | toutes les 30 min, et après la tournée |
| Compilations longues | chaque dimanche |
| État des connexions | toutes les 3 h |
| Brancher une chaîne YouTube | à la demande |

Briques libres : Kokoro et voix Edge, faster-whisper, Depth Anything V2, Real-ESRGAN, CLIP (ONNX), Pollinations,
Wikimedia Commons, Mixkit, polices OFL / Apache. Voir `squabot/polices/LICENCES.md`.
