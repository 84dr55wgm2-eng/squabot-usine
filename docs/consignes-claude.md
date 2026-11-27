# Consignes pour Claude : écrire les prochaines vidéos

Claude (abonnement, tâche planifiée) fait la « tournée » : il lit les comptes actifs, la boîte à idées et ce qui est
déjà prévu, puis écrit de nouveaux fichiers `data/videos/<date>-<sujet>/video.json` avec `"statut": "a_fabriquer"`.
GitHub Actions fabrique ensuite les vidéos seul.

## Tournée

1. `python -m squabot verifier` doit répondre OK.
2. Pour chaque compte `actif: true` de `comptes/`, compter les vidéos prévues dans les 7 prochains jours
   (`date_prevue`). En écrire de nouvelles jusqu'à atteindre `rythme.videos_par_jour` × 7.
3. Prendre d'abord les idées de `data/idees/idees.yaml` (statut `nouvelle`) du compte, sinon chercher un sujet dans
   les sources du thème. Passer l'idée utilisée à `statut: utilisee`.
4. Ne jamais reprendre un sujet déjà traité par le même compte (regarder les `titre` existants).
5. Commiter et pousser. Rien d'autre.

## Règles de contenu (obligatoires)

- Respecter `ton`, `regles`, `niveau` et `verite` du thème. Le niveau de la vidéo = celui du thème.
- `verite: verifiee` : chaque fait vient d'une source citée dans `sources` (pages lues, pas de mémoire).
  En cas de doute, retirer le fait.
- `verite: virale-non-verifiee` : raconter avec nos mots, changer prénoms et détails identifiants, et l'écrire dans
  la description (« histoire trouvée sur internet, non vérifiée »).
- Jamais : personne privée nommée, mineur, victime identifiable, image de violence explicite, nudité,
  copie du texte ou de la vidéo d'un autre créateur.
- `adulte` : personnages adultes et fictifs, visuels suggestifs non explicites, uniquement pour les comptes adultes.

## Ne pas être « contenu produit en masse »

YouTube démonétise les chaînes dont les vidéos se ressemblent toutes (règle « contenu inauthentique »). Chaque vidéo doit
avoir son angle, ses faits vérifiés et sa forme. Concrètement, dans `video.json` :

- `"forme"` : une des formes de `squabot/strategie.yaml` (récit, liste, enquête, vrai/faux, avant/après, chronologie,
  comparaison, question, portrait, actu). Jamais 3 fois de suite la même ; vise au moins 4 formes sur 10 vidéos.
- Accroche : alterne question, chiffre, scène, citation, affirmation choc, défi.
- Titre : pas le même modèle (« Le jour où… ») plus de 2 fois sur les 10 dernières vidéos.
- Suite de plans : réorganise (ne commence pas toujours par un `titre`, place la `fiche` ou le `compteur` ailleurs).

`python -m squabot verifier` mesure tout ça et bloque une vidéo trop proche des précédentes ;
`python -m squabot variete` donne le risque de chaque chaîne (0-100 : < 35 sain, > 60 danger). L'habillage visuel
(position et style des sous-titres, ordre des transitions, grain) change déjà seul d'une vidéo à l'autre.

## Rétention (voir `squabot/strategie.yaml`)

- 2 premières secondes : la promesse concrète ou l'image choc, 12 mots maximum, aucune salutation.
- Une relance toutes les 15 s environ ; la réponse à la fin ; la dernière phrase peut boucler sur la première.
- Rien d'immobile plus de 3 s à l'écran.
- `epingle` : une question simple à épingler en commentaire pour lancer la discussion.

## Registre (`registre` du compte)

- `jeune` (par défaut) : on parle à des 18-30 ans. Tutoiement, phrases très courtes, rythme de conversation.
  Expressions courantes et naturelles, **une ou deux par vidéo, jamais forcées** : « franchement », « attends »,
  « le truc, c'est que… », « c'est chaud », « de ouf », « j'avoue », « grave », « en vrai ». Accorde-les à l'`accent`
  de la voix : fr-CA (« pantoute », « pis », « c'est malade »), fr-BE (« savoir » pour « pouvoir », « non peut-être »),
  fr-CH (« ça joue », « tout de bon »), en-GB (« proper », « mad »), en-AU (« heaps », « reckon »), es-MX (« neta »,
  « qué onda »), es-AR (« re », « che »), es-ES (« flipante », « tío »). Jamais de verlan lourd, d'argot qui vieillit
  vite ni de faute volontaire ; les faits restent exacts et sourcés.
- `neutre` : vouvoiement ou forme impersonnelle, ton documentaire vivant.
- `pose` : voix grave et lente, phrases plus longues, ambiance (horreur, mystère, histoire).

## Écrire humain, pas « IA »

Les tics qui trahissent un texte de machine sont interdits :
« Et le pire ? … », « Mais attendez… », « Accrochez-vous », « Croyez-le ou non », « Spoiler : », « Plot twist »,
« Dans un monde où… », « Imaginez un instant », « Ce n'est pas tout », trois adjectifs à la suite, une question
rhétorique suivie d'un silence, « véritable » et « incroyable » à chaque phrase.
Écris comme on parle : « Et le pire, c'est que personne n'a rien vu. » Des phrases qui s'enchaînent, des liaisons
naturelles (« du coup », « sauf que », « bref »), des détails concrets plutôt que des superlatifs.
La voix lit le texte « oral » produit par `squabot/oral.py` (élisions jeunes, lettres muettes corrigées) : écris en
français correct, la conversion est automatique, et les sous-titres gardent le texte écrit.

## Script

- Dans la langue de la chaîne (`langue`), parlé, phrases courtes, une phrase par ligne (`\n`). Accroche choc dans la première ligne.
- Durée : environ 2,6 mots par seconde. **Cible : 165 à 195 mots (62 à 75 s)** : au-dessus de 61 s la vidéo est
  rémunérée par TikTok, et elle reste un Short valable sur YouTube (jusqu'à 3 min). Ne descends sous 61 s que si le
  compte ne publie pas sur TikTok.
- Chiffres en lettres quand ils doivent être prononcés naturellement, sauf les années (« En 1911 »).
- Dernière ligne : chute ou révélation, pas de « abonne-toi ».

## Plans

Un plan par idée, 1,5 à 4 s, jamais plus de 5 s sans changement. Chaque plan commence aux mots `a` (recopiés
exactement du script, dans l'ordre). Types :

| type | champs | usage |
|---|---|---|
| `titre` | `grand`, `petit`, `prompt` (fond facultatif) | date, lieu, chiffre d'ouverture |
| `photo` | `fichier` (nom exact sur Wikimedia Commons), `camera`, `focus` | personne ou lieu réel ; si introuvable, `prompt` sert de secours |
| `illustration` | `prompt` (anglais, la scène seulement : le style vient du thème), `camera`, `focus`, `graine` | scènes sans photo |
| `fiche` | `lignes` (titre, nom, 1-2 détails) | présenter une personne, un suspect, un dossier |
| `compteur` | `de`, `a_valeur`, `prefixe`, `unite`, `legende` | durée, somme, nombre qui monte |

Options sur tous les plans : `texte` (gros mot à l'écran, 1-3 mots), `sous_texte`, `tampon: {texte, a}`
(tampon rouge qui s'écrase sur le mot `a`, 1 ou 2 mots). `camera` : `avance`, `recule`, `gauche`, `droite`,
`monte`, `fixe`. `focus` : hauteur du point d'intérêt (0 = haut, 1 = bas).

Prompts d'illustration : concrets (qui, quoi, où, lumière), pas de texte dans l'image. **Jamais une œuvre célèbre
ni une personne réelle générée par l'IA** (le résultat est faux et se voit) : utilise leur vraie photo, le montage
fera les gros plans tout seul. Pour une `recherche`, ajoute `decrit` : une phrase en anglais de ce que la photo doit
montrer ; l'analyse d'image (CLIP) rejette les photos hors sujet et passe alors au `prompt` de secours.

## Exemple

Voir `data/videos/2026-11-25-vol-joconde/video.json`.

## Vidéos faites de clips réels (posts X)

1. **Regarder avant d'écrire.** Lancer `regarder.yml` avec les liens des posts (ou `python -m squabot x regarder <liens>`),
   puis ouvrir `data/x/vus/<id>/planche_1.jpg` (une image par seconde, minutée) et lire `vu.json` (paroles).
2. **Le texte décrit ce qu'on voit.** Chaque phrase correspond à un passage précis du clip : jamais de détail
   inventé à partir de la seule légende du post.
3. **Un plan par passage.** Pour chaque phrase : `{"x": lien, "debut": secondes}` pris sur la planche, au moment
   où l'action dite commence. Couper en deux plans dès que la phrase raconte deux moments (« … et quand elle revient »).
4. La source est affichée automatiquement (« @compte sur X ») et citée dans la description.
