# My-art — comprendre les œuvres d’art

My-art est un prototype de musée interactif qui aide à découvrir un tableau sans connaissances préalables en histoire de l’art. Le visiteur choisit une œuvre, pose une question ou suit une visite guidée. Les explications s’appuient sur des documents fournis avec l’œuvre et peuvent être accompagnées de vues pédagogiques pour guider le regard.

L’objectif est une médiation simple, sourcée et accessible : expliquer ce que l’on regarde, permettre d’approfondir et rendre les limites des sources visibles.

## État du projet

Le parcours actuel est un **POC local Python / Streamlit avec Amazon Bedrock**. Le corpus de l’œuvre est transmis directement au modèle : il n’y a pas encore de recherche RAG avec index ou embeddings.

| Disponible | À développer ou à évaluer |
| --- | --- |
| Catalogue local et import d’œuvres | Administration et déploiement pour les visiteurs |
| Questions et visites en français, niveau simple ou détaillé | Mémoire conversationnelle et parcours multilingues |
| Documents TXT, Markdown et PDF textuels, citations contrôlées | Recherche documentaire pour des corpus plus grands, OCR |
| Analyse facultative de l’image par Nova | Qualité des interprétations et accessibilité auprès des publics |
| Affichage de vues préparées via un fournisseur simulé | Génération d’images intégrée et validation des vues |
| Interface Streamlit, CLI et aperçus sans réseau | Audio, reconnaissance d’œuvres depuis une photo |

**Deux usages distincts sont conservés :**

- Le musée utilise Bedrock pour les explications et des images déjà préparées pour les vues. Il n’appelle pas OpenAI.
- Le module facultatif `my_art.generate_views` génère des variantes d’un tableau avec OpenAI Images. Cette expérimentation est conservée et testée, mais n’est pas branchée au parcours du musée.

## Démarrage rapide

Python **3.10 ou ultérieur**, depuis la racine du dépôt. Commandes PowerShell :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m my_art visit het-steen --dry-run
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Si `.venv` existe déjà, sautez sa création. Sous Linux/macOS, utilisez `python3 -m venv .venv`, `.venv/bin/python` et des chemins avec `/`.

Le dépôt fournit les ressources de **Het Steen** dans `data/artworks/het-steen/` et `data/documents/het-steen/`. L’aperçu `--dry-run` et le bouton **Vérifier le contexte — sans appel API** fonctionnent sans identifiants. Ils préparent les sources sans produire d’explication IA.

Pour demander une explication, créez votre `.env` à partir de [.env.example](.env.example), uniquement s’il n’existe pas, puis configurez Bedrock selon le [guide dédié](docs/guides/bedrock.md). Une demande déclenche au maximum un appel Bedrock facturable.

```powershell
.\.venv\Scripts\python.exe -m my_art ask het-steen "Que voit-on au premier plan ?"
.\.venv\Scripts\python.exe -m my_art mock-image het-steen foreground
```

Pour essayer les deux corpus **fictifs**, utilisez un catalogue distinct :

```powershell
.\.venv\Scripts\python.exe -m my_art --data-dir data/demo init-demo
.\.venv\Scripts\python.exe -m my_art --data-dir data/demo visit demo-port --dry-run
```

`init-demo` nécessite un dossier vide. L’option globale `--data-dir` se place avant la commande ; l’interface utilise `MUSEUM_DATA_DIR` dans `.env`.

## Ajout automatique d’œuvres et d’images

Déposez les images dans `data/artworks/<identifiant>/` et les documents TXT, Markdown ou PDF textuels dans `data/documents/<identifiant>/`. Les dossiers sont également relatifs à `MUSEUM_DATA_DIR` si vous avez configuré un autre catalogue.

- **Original** : une image portant l’identifiant du dossier (tirets ou underscores), puis `original`, puis l’unique autre image disponible. Extensions reconnues : JPG, JPEG, PNG et WEBP, sans distinction de casse.
- **Vues** : `firstplan` / `premier_plan` / `foreground`, `secondplan` / `second_plan` / `midground`, `arriere_plan` / `background` et `detail`.
- **Notice** : `metadata.json` permet de préciser le titre, l’artiste, les descriptions et les fichiers à utiliser. Ses choix explicites restent prioritaires. Sans notice, le titre vient du dossier et l’artiste reste « Artiste non renseigné ».

L’interface surveille les ajouts, modifications et suppressions toutes les **3 secondes** tant que la session est active. Le catalogue est également relu à chaque commande CLI. Aucun appel IA n’est déclenché par cette détection et aucune notice n’est réécrite.

En cas de plusieurs fichiers candidats au même rang, précisez le champ `image` ou `views` dans la notice. Les fichiers reconnus comme vues ne sont pas choisis comme original. Une association par nom de fichier ne valide pas le contenu artistique de l’image.

## Générer plusieurs vues d’un tableau

Installation facultative et simulation locale :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/imagegen.txt
.\.venv\Scripts\python.exe -m my_art.generate_views "data\artworks\het-steen\het_steen.jpg" --dry-run
```

Sans `--dry-run`, le module nécessite `OPENAI_API_KEY` et effectue un appel d’édition par vue demandée. Chaque édition repart de l’original. Les sorties sont enregistrées dans `output/imagegen/` et restent à relire visuellement. Le [guide de génération](docs/guides/image-generation.md) décrit les options, la configuration et les résultats.

## Organisation du dépôt

```text
My-art/
├── app.py                 # Lanceur Streamlit
├── my_art/                # Code Python : interface, CLI, métier et fournisseurs
│   └── generate_views.py  # Expérimentation image autonome
├── data/                  # Catalogue actif : images, notices et documents
├── examples/museum/       # Deux corpus fictifs pour les tests et init-demo
├── evaluation/            # Questions de référence pour la relecture des modèles
├── tests/                 # Tests automatisés sans appels API réels
├── requirements/          # Dépendances communes, musée, images et développement
├── docs/                  # Architecture, développement, feuille de route et guides
├── requirements.txt       # Installation du musée
└── .env.example           # Modèle de configuration locale
```

Le dossier `data/` contient le catalogue actif et ses ressources versionnées. `examples/` contient les corpus fictifs. Les dossiers `output/` (résultats), `input/` (images personnelles), `.venv/` et le fichier `.env` sont exclus de Git.

## Développer et vérifier

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les tests simulent les fournisseurs et couvrent les citations, l’isolation des œuvres, les imports, les vues, l’interface et le générateur d’images. Ils ne mesurent ni la qualité artistique ni les accès réels aux services.

## Documentation

- [Architecture actuelle](docs/architecture.md) : responsabilités, flux et contrats d’extension.
- [Guide Bedrock](docs/guides/bedrock.md) : configuration, données et commandes.
- [Guide Het Steen](docs/guides/het-steen.md) : ressources fournies et simulation des vues.
- [Génération d’images](docs/guides/image-generation.md) : expérimentation OpenAI indépendante.
- [Développement et migration](docs/development.md) : dépendances, tests et nouveaux chemins.
- [Vision et feuille de route](docs/roadmap.md) : objectifs, prochaines étapes et critères d’évaluation.
- [Évaluation](evaluation/README.md) : utilisation des questions de référence.

Le contrôle des références ne garantit pas la justesse d’une interprétation. Les explications et vues doivent être relues. L’interface reste un banc de test local, sans authentification ni conformité d’accessibilité revendiquée.


## Parcours accessible et documents personnels

La visite guidée est sélectionnée par défaut. Une visite validée contient exactement
**trois parties**, affichées une à la fois : présentation générale (peintre, date et
contexte documentés), premier plan, second plan. Les étapes de plans affichent
uniquement leur vue préparée. Une vue manquante est signalée sans la remplacer
par l’original. L’original reste accessible dans la présentation générale.

Le niveau **Simple** demande des phrases courtes, un vocabulaire concret et 40 à
80 mots par partie. Le niveau **Détaillé** demande 150 à 250 mots par partie si les
sources le permettent. Ces longueurs sont des consignes au modèle, pas une garantie.
L’ordre des trois parties et les citations sont contrôlés avant affichage.

Les documents sont associés à chaque œuvre par son identifiant. Trois emplacements
sont lus ensemble, sans mélanger les tableaux :

- `data/documents/<identifiant>/` (emplacement historique conservé) ;
- `data/artworks/documents/<identifiant>/` ;
- `data/artworks/<identifiant>/documents/`.

Le dossier réservé `data/artworks/documents/` ne devient pas une œuvre du catalogue.
Les TXT sont en UTF-8. Dans l’interface, le visiteur peut aussi ajouter des TXT avant
la génération : 10 fichiers maximum de 1 Mo chacun, dans la limite totale du
contexte de 40 000 caractères et 150 passages. Les fichiers ajoutés ne sont pas
installés dans le catalogue. Leur texte est envoyé au modèle lors de la demande
et conservé dans le JSON local du résultat, avec les citations et leur provenance.

Le sélecteur **Contraste des images** propose Normal, Élevé (high contrast) et
Doux (low contrast). Il ajuste l’affichage sans modifier les fichiers ni l’image
transmise au modèle. Il ne constitue pas une correction universelle du daltonisme.

La consigne commune est centralisée dans `my_art/master_prompt.txt`. Bedrock
l’applique automatiquement aux questions et aux visites ; l’utilisateur n’a rien
à copier. Elle est consultable dans la barre latérale.

Le générateur autonome propose désormais `premier_plan`, `second_plan`,
`arriere_plan` et `detail` (quatre éditions par défaut). Pour ne préparer que les
deux plans de la visite, utiliser `--views premier_plan second_plan`. Après
vérification humaine, placer ces PNG dans le dossier de l’œuvre : la découverte
automatique reconnaît leurs noms. La génération à la volée reste séparée de
l’interface du musée.
