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
.\.venv\Scripts\python.exe -m my_art import-artwork "art_gallery\het-steen"
.\.venv\Scripts\python.exe -m my_art visit het-steen --dry-run
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Si `.venv` existe déjà, sautez sa création. Sous Linux/macOS, utilisez `python3 -m venv .venv`, `.venv/bin/python` et des chemins avec `/`.

Le dépôt fournit **Het Steen**, ses deux textes et deux vues préparées. L’import les copie dans `data/` et refuse d’écraser des fichiers différents. L’aperçu `--dry-run` et le bouton **Vérifier le contexte — sans appel API** fonctionnent sans identifiants. Ils préparent les sources sans produire d’explication IA.

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

## Générer plusieurs vues d’un tableau

Installation facultative et simulation locale :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/imagegen.txt
.\.venv\Scripts\python.exe -m my_art.generate_views "art_gallery\het-steen\het_steen.jpg" --dry-run
```

Sans `--dry-run`, le module nécessite `OPENAI_API_KEY` et effectue un appel d’édition par vue demandée. Chaque édition repart de l’original. Les sorties sont enregistrées dans `output/imagegen/` et restent à relire visuellement. Le [guide de génération](docs/guides/image-generation.md) décrit les options, la configuration et les résultats.

## Organisation du dépôt

```text
My-art/
├── app.py                 # Lanceur Streamlit
├── my_art/                # Code Python : interface, CLI, métier et fournisseurs
│   └── generate_views.py  # Expérimentation image autonome
├── art_gallery/het-steen/ # Ressources réelles fournies, à importer
├── examples/museum/       # Deux corpus fictifs pour les tests et init-demo
├── evaluation/            # Questions de référence pour la relecture des modèles
├── tests/                 # Tests automatisés sans appels API réels
├── requirements/          # Dépendances communes, musée, images et développement
├── docs/                  # Architecture, développement, feuille de route et guides
├── requirements.txt       # Installation du musée
└── .env.example           # Modèle de configuration locale
```

Les dossiers locaux `data/` (catalogue actif), `output/` (résultats), `input/` (images personnelles), `.venv/` et le fichier `.env` sont exclus de Git. `art_gallery/` et `examples/` sont les ressources versionnées ; les imports ne les modifient pas.

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
