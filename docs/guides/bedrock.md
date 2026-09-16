# Premier POC : documentation et visite avec Bedrock

[Accueil](../../README.md) · [Architecture](../architecture.md)

Cette version permet de tester l'explication des œuvres avec les modèles Nova déjà disponibles. Les documents d'une œuvre sont intégralement joints à la demande, dans une limite explicite. **Ce n'est pas encore un RAG vectoriel** : aucun embedding, index distant ou modèle externe n'est requis.

## Ce qui fonctionne

- Catalogue local d'œuvres, image de référence facultative.
- Documents Markdown, texte UTF-8 et PDF avec texte extractible, isolés par œuvre.
- Questions-réponses et visite guidée en français, niveau simple ou détaillé.
- Analyse visuelle facultative avec Nova Pro, Lite ou Nova 2 Lite.
- Réponse structurée avec passages cités, distinction entre documentation et observation visuelle.
- Sélection de vues pédagogiques préparées via un appel de génération simulé, sans API image.
- Interface Streamlit locale et commandes Python.
- Aperçu sans réseau, tests simulés, traces locales et un seul appel Bedrock par demande.

Les modèles sélectionnables sont `eu.amazon.nova-pro-v1:0` (défaut), `eu.amazon.nova-lite-v1:0`, `eu.amazon.nova-2-lite-v1:0` et `eu.amazon.nova-micro-v1:0` (texte seul). Ce sont des configurations candidates ; leur accès réel et la qualité pédagogique restent à tester avec votre compte et vos œuvres. Aucun basculement automatique vers un autre modèle n'est effectué.

## Démarrage sous Windows / PowerShell

Depuis la racine du dépôt, avec Python 3.10 ou ultérieur :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si l'environnement `.venv` existe déjà, sautez la première commande. Ces dépendances sont indépendantes du script expérimental OpenAI `my_art/generate_views.py`, qui reste disponible avec `requirements/imagegen.txt` mais n'est jamais appelé par le musée.

Pour découvrir le fonctionnement sans tableau réel ni identifiants :

```powershell
.\.venv\Scripts\python.exe -m my_art init-demo
.\.venv\Scripts\python.exe -m my_art list
.\.venv\Scripts\python.exe -m my_art visit demo-port --dry-run
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Ouvrez l'adresse locale affichée, normalement `http://127.0.0.1:8501`. Choisissez une œuvre, une question ou une visite guidée, puis **Vérifier le contexte — sans appel API**. Aucun client AWS n'est créé pendant cet aperçu. Les deux œuvres de démonstration sont entièrement fictives, sans image, et clairement identifiées comme telles.

`init-demo` copie les exemples dans le dossier de données uniquement s'il est vide. Il ne remplace jamais un catalogue existant.

## Configurer AWS

Ajoutez les variables suivantes à votre `.env` local, sans écraser les éventuelles autres clés :

```dotenv
AWS_REGION=eu-west-3
BEDROCK_MODEL_ID=eu.amazon.nova-pro-v1:0
MUSEUM_DATA_DIR=data
```

La région est un exemple à adapter à votre accès Bedrock et au profil d'inférence EU. Deux méthodes d'authentification sont possibles :

**Clé API Bedrock** : créez-la dans la console Amazon Bedrock, puis ajoutez localement :

```dotenv
AWS_BEARER_TOKEN_BEDROCK=votre_cle_bedrock
```

**Profil AWS IAM ou SSO** : configurez-le avec votre procédure AWS habituelle et ajoutez :

```dotenv
AWS_PROFILE=mon-profil
```

Dans ce second cas, ne renseignez pas `AWS_BEARER_TOKEN_BEDROCK`. Renouvelez la session SSO si nécessaire avec `aws sso login --profile mon-profil`. Les identifiants temporaires IAM et rôles d'exécution sont aussi pris en charge par la chaîne d'authentification Boto3 standard. Le `.env` situé à la racine du projet est chargé sans remplacer les variables d'environnement déjà définies.

La clé Bedrock n'est ni une clé OpenAI ni un accès Amazon Polly. Les droits doivent autoriser l'inférence Bedrock, notamment les modèles et destinations du profil d'inférence EU. Les appels sont facturés sur AWS selon votre compte ; ChatGPT Plus n'intervient pas.

Références AWS : [utiliser une clé Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-use.html), [création d'une clé](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-generate.html), [sorties par outil Nova](https://docs.aws.amazon.com/nova/latest/userguide/tool-use-definition.html).

## Ajouter une vraie œuvre

Le tableau Het Steen et ses vues préparées sont disponibles : voir le [guide du test Het Steen](het-steen.md) pour l'import et la simulation sans réseau.

Le dossier administrateur par défaut est `data/`, exclu de Git :

```text
data/
├── artworks/
│   └── oeuvre-001/
│       ├── metadata.json
│       └── original.jpg
└── documents/
    └── oeuvre-001/
        ├── notice.md
        └── dossier.pdf
```

Exemple de `metadata.json` à adapter :

```json
{
  "id": "oeuvre-001",
  "title": "Titre de l'œuvre",
  "artist": "Nom de l'artiste ou attribution inconnue",
  "image": "original.jpg",
  "image_alt": "Description factuelle de l'image pour les visiteurs.",
  "demo": false
}
```

L'identifiant du dossier et celui de la notice doivent correspondre. `image` peut être `null` pour commencer par le texte. Renseignez dans les documents l'auteur ou l'institution source, les références d'origine, les droits et les informations historiques que le modèle sera autorisé à expliquer. Les métadonnées du catalogue ne remplacent pas les sources documentaires.

Les fichiers sont relus à chaque demande. Les passages ont des identifiants dérivés de leur œuvre, document, emplacement et contenu. Une empreinte identifie la version du corpus utilisée ; aucune réindexation manuelle n'est nécessaire.

Limites volontaires pour le premier test : 30 fichiers, 10 Mio par document, PDF de 50 pages maximum, 40 000 caractères de texte et 150 passages par œuvre. Un corpus trop long est refusé, sans troncature cachée. Un PDF contenant des pages sans texte extractible est refusé : préparez une version texte/OCR vérifiée. Il n'y a pas encore d'OCR intégré. Les images de 20 Mio maximum sont préparées en JPEG, orientées selon EXIF et réduites à 1 600 pixels sur le plus grand côté pour l'analyse ; le fichier original n'est pas modifié.

## Lancer les premiers appels

Dans l'interface, cliquez sur **Demander l'explication — appel Bedrock**. Les changements de sélection et les téléchargements ne relancent pas le modèle. Chaque demande est indépendante : pas de mémoire conversationnelle entre questions à ce stade.

En ligne de commande :

```powershell
.\.venv\Scripts\python.exe -m my_art ask demo-port "Que voit-on au premier plan ?"
.\.venv\Scripts\python.exe -m my_art visit demo-port --level detaille
.\.venv\Scripts\python.exe -m my_art ask demo-port "Quelle est sa date ?" --text-only --model eu.amazon.nova-micro-v1:0
```

La dernière question teste une information volontairement absente de la notice : le résultat attendu est un refus documentaire ou une réponse sourcée expliquant que la date n'est pas renseignée.

Les fichiers `output/museum/<identifiant>/result.json` conservent la demande, les documents utilisés, leurs références, le modèle, l'empreinte de l'image envoyée, la réponse et l'usage retourné par AWS. Ces traces contiennent le corpus documentaire : elles sont locales, exclues de Git, et doivent être traitées selon les droits des documents. Aucun secret n'est enregistré.

Il n'y a ni relance automatique ni appel de réparation lorsqu'une réponse est invalide. Après une erreur ou un délai dépassé, un appel peut néanmoins avoir été facturé ; vérifiez votre usage avant de recommencer.

## Architecture et limites de fiabilité

L’[architecture actuelle](../architecture.md) décrit les modules, le flux de données et les contrats de fournisseurs. Le musée suit une séquence fixe : préparation du contexte, appel à Nova, validation des citations, puis sélection des vues locales. Il n’exécute pas de boucle d’agents autonomes.

Le contrôle refuse les références inconnues, les citations absentes des passages, les affirmations documentaires sans référence et les observations visuelles sans image. Il ne prouve pas qu'une citation étaye réellement toutes les affirmations de l'étape. Le modèle peut encore faire une mauvaise interprétation, ignorer une contradiction ou confondre un détail. Une relecture humaine reste nécessaire. Les instructions de séparation entre données et consignes réduisent les risques d'injection documentaire sans les éliminer.

L'interface est un banc de test local, sans authentification administrateur et sans conformité d'accessibilité revendiquée. Ne la publiez pas telle quelle : une interface destinée aux visiteurs nécessitera des contrôles d'accès, une revue d'accessibilité et une politique de données.

Les prochaines évolutions et leurs critères de validation sont regroupés dans la [feuille de route](../roadmap.md). Le champ `capabilities` des résultats distingue les fonctions disponibles de celles qui restent à implémenter.

## Vérification sans identifiants ni coût API

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_museum.py" -v
```

Les tests emploient le validateur du SDK Bedrock avec réponses simulées et le banc de test Streamlit. Ils couvrent le contexte, l'isolation entre œuvres, les citations inventées, les échecs, le mode sans image et l'interface. Les tests du script OpenAI restent séparés dans `test_generate_views.py` et nécessitent `requirements/imagegen.txt`.

Le [jeu de questions de référence](../../evaluation/bedrock-questions.json) permet ensuite de comparer les modèles sur les deux corpus fictifs. Les résultats réels de qualité, coût et latence ne sont pas encore mesurés.
