# Squabot autonome : comment tout tourne sans toi

Objectif : des vidéos qui sortent et font des vues, sur plusieurs comptes et réseaux, sans action de ta part.
Seule dépense : l'abonnement Claude, utilisé la nuit et plafonné pour ne pas gêner ton usage quotidien.

## Les 7 étages

| # | Étage | Qui | Quand | Coût |
|---|---|---|---|---|
| 1 | **Veille du monde** : ce qui se passe, ce qui buzze, par thème | GitHub Actions (script) | toutes les 6 h | 0 € |
| 2 | **Cerveau** : choisit les sujets, lit les sources, écrit script et plans | Claude (abonnement, `claude-code-action`) | 1 tournée la nuit | abonnement |
| 3 | **Médias** : photos, vidéos libres, illustrations, musique | GitHub Actions | à la fabrication | 0 € |
| 4 | **Usine** : voix, montage, son, miniature, contrôle qualité | GitHub Actions | à la fabrication | 0 € |
| 5 | **Diffusion** : publication, stories | GitHub Actions + navigateur automatique | heures de pointe | 0 € |
| 6 | **Communauté** : lecture et réponse aux commentaires | Claude (tournée de nuit) + script | 1 fois par jour | abonnement |
| 7 | **Mesure** : vues, rétention, abonnés → retour au cerveau | GitHub Actions | 1 fois par jour | 0 € |

## 1. Veille du monde (sans Claude)

Un script rassemble chaque jour, par thème, une liste de sujets candidats dans `data/veille/` :

- **Actualité** : Google Actualités en RSS par mots-clés du thème (gratuit, sans clé).
- **Réseaux** : Reddit (les meilleurs posts du jour des communautés du thème, en JSON public),
  YouTube (recherche et tendances par `yt-dlp`, sans clé : titres, vues, durées des vidéos qui marchent).
- **Encyclopédie** : Wikipédia « ce jour-là » et articles les plus lus du jour.
- **Asie et monde** : listes « hot » de 60 plateformes (Weibo, Douyin, Bilibili, Zhihu, Hacker News…) via
  `imsyy/DailyHotApi` (MIT, 4 k★) ou `newsnext/newsnow` (MIT, 22 k★), lancés dans GitHub Actions.
- **Flux à la carte** : `DIYgod/RSSHub` (47 k★) transforme presque n'importe quel site en flux.
- **Tes liens** : la boîte à idées du tableau de bord (𝕏 lu par fxtwitter, TikTok, Facebook, Reddit).

Chaque candidat est noté : fraîcheur, popularité, adéquation au thème, déjà traité ou non.

## 2. Cerveau : Claude la nuit

`anthropics/claude-code-action` (MIT, 10 k★) fait tourner Claude Code dans GitHub Actions **avec ton abonnement**
(jeton créé une fois par `claude setup-token`). Réglages pour épargner ton usage du jour :

- une tournée vers 3 h, modèle Sonnet, nombre de vidéos plafonné par nuit ;
- tout le reste (veille, médias, montage, publication, stats) tourne **sans** Claude.

Pendant la tournée, Claude :
1. lit la veille, les stats de la semaine et les règles de chaque compte ;
2. choisit les sujets (ce qui marche, ce qui est frais, jamais un doublon) ;
3. lit les sources, écrit le script sourcé et les plans (`docs/consignes-claude.md`) ;
4. **relit les planches-contacts** des vidéos fabriquées la veille (Claude voit les images) et corrige ce qui cloche ;
5. prépare les réponses aux commentaires.

## 3. Médias

| Besoin | Source | Droits |
|---|---|---|
| Photos réelles, archives | Wikimedia Commons, Openverse | libres (crédit automatique) |
| Vidéos réelles | Wikimedia Commons, Internet Archive (domaine public), vidéos YouTube sous licence Creative Commons (filtre de recherche, téléchargées par `yt-dlp`) | libres |
| Scènes sans photo | Pollinations (sans compte, 1 image / 45 s) ; plan B local : `leejet/stable-diffusion.cpp` | libres |
| Netteté | Real-ESRGAN x4 (ONNX, BSD-3), déjà en place | — |
| Musique | Mixkit par humeur, déjà en place | licence Mixkit, créditée |
| Pertinence des images | CLIP (ONNX) compare chaque image au texte du plan ; Claude vérifie la planche | — |

**« Calquer » une chaîne qui marche** : on copie le **format** (accroche, rythme, durée, structure, titres,
miniatures), pas les fichiers. Remettre en ligne la vidéo d'un autre déclenche Content ID, des avertissements
(3 = chaîne supprimée) et la démonétisation pour « contenu réutilisé ». Le format « commentaire » reste possible :
des extraits courts, transformés par notre récit et notre montage (méthode de `linyqh/NarratoAI`, MIT, 12 k★).
`yt-dlp` télécharge aussi des vidéos de référence pour **analyser** leur rythme (nombre de plans, durée des plans,
accroche), sans les republier.

## 4. Usine (en place)

Voix Microsoft (repli Kokoro), calage mot à mot, 2 à 3 s par visuel selon le thème (`densite`),
gros plans automatiques, 2.5D, transitions, texte animé, tampons, fiches avec photo, musique, miniature,
aperçu 720p. À ajouter : vrais extraits vidéo, cartes animées (lieux, trajets), version longue TikTok (> 61 s),
traduction automatique en anglais et espagnol (même vidéo, autre voix : 3 fois plus d'audience pour presque rien).

## 5. Diffusion

- **YouTube** : API officielle (gratuite). Jeton OAuth gardé dans les secrets GitHub. Sans l'audit de Google, les
  vidéos envoyées restent privées : on demande l'audit une fois.
- **TikTok, Facebook, Instagram, 𝕏** : navigateur automatique déjà connecté (méthode `dreammis/social-auto-upload`,
  MIT, 17 k★) ; cookies gardés dans les secrets. Risque : demande de reconnexion ou blocage depuis les serveurs de
  GitHub. On teste d'abord sur un compte d'essai.
- **Stories** : Instagram et Facebook (navigateur), YouTube n'en a plus. Une story par vidéo : extrait de 10 s +
  « nouvelle vidéo ».
- **Horaires** : heures de pointe par réseau, ajustées par les stats.

## 6. Communauté

Chaque nuit, les nouveaux commentaires (API YouTube, navigateur pour les autres) sont lus par Claude :
réponse automatique aux simples (merci, question factuelle sourcée), signalement des autres dans le tableau de bord.
Jamais de réponse aux sujets sensibles sans validation.

## 7. Mesure

Vues, durée de visionnage, rétention, abonnés par vidéo et par réseau, dans `data/stats/`. Le cerveau s'en sert :
plus de sujets et de formats qui marchent, moins des autres.

## Ce qu'il te reste à faire, une seule fois

1. `claude setup-token` sur ton Mac, puis coller le jeton dans les secrets du dépôt (guidé).
2. Créer les comptes sur chaque réseau et t'y connecter une fois.
3. Décider si le dépôt devient public (minutes GitHub illimitées et tableau de bord en ligne gratuit).

## Projets étudiés (novembre 2026)

| Projet | ★ | Ce qu'on en tire |
|---|---|---|
| `harry0703/MoneyPrinterTurbo` (MIT) | 145 k | chaîne sujet → Short, la référence chinoise |
| `NanmiCoder/MediaCrawler` | 72 k | collecte Douyin, Xiaohongshu, Bilibili, Weibo, Zhihu (licence non commerciale : méthode seulement) |
| `DIYgod/RSSHub` (AGPL) | 47 k | tout site en flux |
| `gitroomhq/postiz-app` (AGPL) | 42 k | planificateur multi-réseaux (demande un serveur) |
| `newsnext/newsnow` (MIT) | 22 k | tendances en temps réel, 40+ sources |
| `dreammis/social-auto-upload` (MIT) | 17 k | publication par navigateur (TikTok, YouTube, Douyin…) |
| `krillinai/OpenCreator` (Apache-2.0) | 14 k | traduction et doublage des vidéos en 120 langues |
| `HKUDS/ViMax` (MIT) | 13 k | agents réalisateur / scénariste / producteur |
| `linyqh/NarratoAI` (MIT) | 12 k | commentaire automatique sur des extraits vidéo |
| `anthropics/claude-code-action` (MIT) | 10 k | Claude dans GitHub Actions avec l'abonnement |
| `GuanYixuan/pyJianYingDraft` (Apache-2.0) | 5 k | projets CapCut générés par code |
| `imsyy/DailyHotApi` (MIT) | 4 k | listes « hot » de 60 plateformes |
| `yt-dlp/yt-dlp` (Unlicense) | 210 k | téléchargement et analyse vidéo |

Gitee (le GitHub chinois) n'est pas joignable depuis cette machine ; il le sera depuis GitHub Actions pour la suite.
