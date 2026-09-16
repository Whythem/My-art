# Art Agent

Projet Python pour générer une audiodescription ou un fond sonore à partir d'une image / œuvre d'art, en s'appuyant sur :

- un LLM Brain via AWS Bedrock,
- un moteur de RAG local pour enrichir le contexte,
- des outils spécialisés pour l'image, la génération sonore et la synthèse de texte.

## Pré-requis

- Python 3.11 ou une version plus récente ;
- un compte AWS avec des identifiants configurés localement ;
- l'accès au modèle AWS Bedrock indiqué dans `.env` ;
- une image `.jpg`, `.jpeg`, `.png` ou `.webp` à analyser.

Les commandes ci-dessous sont données pour PowerShell sous Windows. Les variantes macOS/Linux sont indiquées lorsqu'elles diffèrent.

## Installation complète

Depuis le dossier qui contient ce README :

```powershell
cd art-agent
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Sous macOS/Linux :

```bash
cd art-agent
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

L'installation avec `-e` permet d'utiliser le code local immédiatement et installe aussi les outils de développement (`pytest`, `ruff` et `mypy`). Pour installer uniquement les dépendances d'exécution, utiliser `python -m pip install -e .`.

Pour quitter l'environnement virtuel :

```powershell
deactivate
```

Pour le réactiver plus tard sous PowerShell :

```powershell
cd art-agent
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloque l'activation des scripts, exécuter une fois :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Configuration AWS et environnement

La solution la plus simple si tu n’as qu’une clé API AWS est d’utiliser directement les variables d’environnement dans le fichier `.env`.

Créer le fichier local `.env` à partir du modèle :

```powershell
Copy-Item .env.example .env
```

Sous macOS/Linux :

```bash
cp .env.example .env
```

Modifier ensuite `.env` avec tes vraies valeurs :

```dotenv
AWS_REGION=eu-west-3
AWS_ACCESS_KEY_ID=VOTRE_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=VOTRE_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN=VOTRE_SESSION_TOKEN_SI_TEMPORELLE
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
RAG_DIR=./data/rag
OUTPUT_DIR=./outputs
LOG_LEVEL=INFO
```

Tu peux aussi utiliser un profil AWS local si tu en as déjà un :

```dotenv
AWS_PROFILE=my-profile
```

Dans ce cas, tu peux configurer le profil avec AWS CLI :

```powershell
aws configure --profile my-profile
aws sts get-caller-identity --profile my-profile
```

Le compte AWS doit avoir l’autorisation d’appeler Bedrock et l’accès au modèle choisi dans la région configurée.

Ne jamais versionner `.env` ni y placer de clés AWS en clair.

## Objectif

Le flux typique est le suivant :

1. Choisir une tâche : `audio-description` ou `background-sound`.
2. Fournir une image dans un dossier d'entrée.
3. Analyser l'image avec un outil dédié.
4. Interroger le RAG pour récupérer du contexte utile.
5. Appeler le LLM via Bedrock pour produire un résultat structuré.
6. Enregistrer la sortie dans le dossier de sortie.

## Structure du projet

- `src/art_agent/cli.py` : point d'entrée CLI.
- `src/art_agent/orchestrator.py` : orchestration du workflow.
- `src/art_agent/llm/` : client Bedrock.
- `src/art_agent/tools/` : outils dédiés à l'image, au RAG, à l'audio.
- `data/rag/` : documents ou corpus fournis au RAG.
- `outputs/` : résultats générés.

## Vérifier l'installation

Avec l'environnement virtuel activé :

```powershell
art-agent version
python -m compileall src
pytest
ruff check src
```

Les tests automatisés ne sont pas encore présents dans le dépôt ; `pytest` peut donc indiquer qu'aucun test n'a été collecté. La compilation, Ruff et la commande `version` vérifient néanmoins l'installation et les erreurs Python de base.

## Tester une génération

Créer un dossier d'images et y placer une image à analyser :

```powershell
New-Item -ItemType Directory -Force samples | Out-Null
```

Puis lancer une audiodescription :

```bash
python -m art_agent.cli generate \
  --image-path ./samples/painting.jpg \
  --task audio-description \
  --rag-dir ./data/rag \
  --output-dir ./outputs
```

Sous PowerShell, utiliser le caractère d'accent grave pour continuer une commande sur plusieurs lignes :

```powershell
python -m art_agent.cli generate `
  --image-path .\samples\painting.jpg `
  --task audio-description `
  --rag-dir .\data\rag `
  --output-dir .\outputs
```

Ou, après installation du package :

```bash
pip install -e .
art-agent generate --image-path ./samples/painting.jpg --task audio-description --rag-dir ./data/rag --output-dir ./outputs
```

Pour produire une direction artistique sonore :

```powershell
art-agent generate `
  --image-path .\samples\painting.jpg `
  --task background-sound `
  --output-dir .\outputs
```

Le résultat est enregistré en Markdown dans `outputs/`, avec un nom basé sur celui de l'image. Le dossier `data/rag/` contient déjà un corpus d'exemple ; il peut être complété avec des fichiers texte `.txt` ou Markdown.

## Commandes utiles

Afficher l'aide de la CLI :

```powershell
art-agent --help
art-agent generate --help
```

Lancer directement le module sans l'installation de l'exécutable :

```powershell
python -m art_agent.cli version
```

Après chaque nouvelle installation ou modification des dépendances, réinstaller avec `python -m pip install -e ".[dev]"` dans l'environnement virtuel.

## Prochaines évolutions prévues

- ajout d'un vrai moteur visuel / OCR / captioning ;
- intégration d'un moteur de synthèse vocale ;
- support d'un RAG vectoriel ;
- version multilangues et gestion des styles artistiques ;
- orchestration plus avancée avec workers / queues.
