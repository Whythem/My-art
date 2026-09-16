# Développer My-art

## Installation

Depuis la racine, avec Python 3.10 ou ultérieur :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/dev.txt
```

Les dépendances sont réparties par usage, sans duplication des bibliothèques communes :

| Fichier | Contenu |
| --- | --- |
| `requirements.txt` | Point d’entrée pour installer le musée. |
| `requirements/base.txt` | Pillow et python-dotenv, partagés. |
| `requirements/museum.txt` | Base, Boto3, Pydantic, pypdf et Streamlit. |
| `requirements/imagegen.txt` | Base et SDK OpenAI ; facultatif. |
| `requirements/dev.txt` | Les deux parcours et HTTPX utilisé directement par les tests. |

Les plages de versions existantes sont conservées. Il n’y a pas encore de verrouillage exact des dépendances ; une installation ultérieure peut résoudre des versions différentes.

## Vérification locale

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q my_art app.py tests
.\.venv\Scripts\python.exe -m pip check
```

Les tests utilisent des catalogues temporaires, le validateur du SDK Bedrock, des réponses simulées et `AppTest` de Streamlit. Aucun appel distant facturable n’est nécessaire.

| Tests | Vérifications principales |
| --- | --- |
| `test_museum.py` | Corpus, provenance, isolation, citations, schéma, adaptateur Bedrock, erreurs et interface. |
| `test_visuals.py` | Import reproductible de Het Steen, intégrité des fichiers, vues disponibles et interface. |
| `test_generate_views.py` | Éditions depuis l’original, PNG, manifest, dry-run et résultats partiels après erreur. |
| `test_entrypoints.py` | Exécution du générateur depuis un autre dossier, dépendances facultatives et configuration. |

Pour un environnement limité au musée, lancez séparément `test_museum.py` et `test_visuals.py` avec `-p`. Pour l’installation image seule, utilisez `-p "test_generate_views.py"`. La suite complète nécessite `requirements/dev.txt`.

Les tests simulés ne prouvent pas l’accès aux modèles, la fidélité artistique ou la qualité pédagogique. Le [protocole d’évaluation](../evaluation/README.md) complète ces contrôles.

## Organisation et conventions

Le [document d’architecture](architecture.md) décrit le rôle de chaque module. Les interfaces appellent `runtime.py` pour assembler le musée et sauvegarder les résultats ; elles ne doivent pas se dépendre mutuellement. Les règles métier restent dans le service et les adaptateurs.

Conservez les données de travail dans `data/`, les fichiers produits dans `output/` et les secrets dans `.env`. Les exemples fictifs doivent être identifiés par `demo: true`. Un nouveau dossier d’œuvre réelle dans `art_gallery/` contient une notice `metadata.json`, ses images et ses documents ; voir les [guides d’import](guides/het-steen.md).

## Migration de l’ancienne organisation

| Avant | Maintenant |
| --- | --- |
| `python generate_views.py ...` | `python -m my_art.generate_views ...` |
| `import generate_views` | `from my_art import generate_views` |
| `pip install -r requirements-bedrock.txt` | `pip install -r requirements.txt` |
| `requirements.txt` pour OpenAI | `requirements/imagegen.txt` pour OpenAI |
| Logique Streamlit dans `app.py` | `my_art/ui.py` ; la commande `streamlit run app.py` reste valable. |
| Fonctions communes dans `my_art.cli` | `my_art.runtime` et `my_art.demo`. |
| `art_gallery/het steen/` | `art_gallery/het-steen/`. |
| `docs/bedrock-poc.md` | `docs/guides/bedrock.md`. |
| `docs/het-steen-poc.md` | `docs/guides/het-steen.md`. |
| `docs/image-generation-test.md` | `docs/guides/image-generation.md`. |

Les notices, images et textes de Het Steen gardent leur contenu et leur identifiant `het-steen`. Les catalogues déjà importés dans `data/`, les résultats dans `output/` et votre `.env` ne nécessitent pas de migration. Le défaut `Settings.region` est harmonisé avec `.env.example` et `Settings.from_env` sur `eu-west-3`.

Le dossier `examples/museum` manquait alors que la CLI, les tests et l’évaluation le référençaient. Les deux notices fictives et leurs métadonnées sont désormais livrées dans le dépôt. Les modules, contrats de fournisseurs, tests, ressources et questions d’évaluation existants ont chacun un usage identifié ; le générateur expérimental est conservé explicitement.
