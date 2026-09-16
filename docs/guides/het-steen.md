# Het Steen : œuvre réelle et génération d'images simulée

[Accueil](../../README.md) · [Architecture](../architecture.md)

Le dossier `art_gallery/het-steen/` contient l'œuvre de Peter Paul Rubens et les ressources fournies pour ce POC :

| Fichier | Utilisation |
| --- | --- |
| `het_steen.jpg` | Référence originale affichée et, si l'option est cochée, envoyée à Nova. |
| `firstplan.png` | Vue pédagogique du premier plan, servie par le simulateur pour `foreground`. |
| `secondplan.png` | Vue pédagogique du second plan et du paysage lointain, servie pour `midground`. |
| `het_steen_overview.txt` | Présentation générale utilisée comme source documentaire. |
| `het_steen_in_depth.txt` | Analyse approfondie utilisée comme source documentaire. |
| `metadata.json` | Notice structurée, descriptions des images et association des vues aux plans. |

Les deux TXT sont déjà compatibles avec le lecteur documentaire. Ils sont conservés en UTF-8, sans réécriture ni traduction, pour préserver les citations. Nova reçoit la consigne d'expliquer en français en conservant les citations dans leur langue d'origine. Les documents fournis ne comportent pas de référence bibliographique complète : elle n'a pas été inventée pendant l'import.

## Importer les ressources

```powershell
.\.venv\Scripts\python.exe -m my_art import-artwork "art_gallery\het-steen"
```

La commande copie la notice et les trois images dans `data/artworks/het-steen/`, et les deux TXT dans `data/documents/het-steen/` (ou le dossier configuré par `MUSEUM_DATA_DIR`). Les fichiers sources restent inchangés. L'import est répétable si les fichiers sont identiques ; il refuse d'écraser une version différente déjà dans le catalogue.

## Tester sans AWS

```powershell
.\.venv\Scripts\python.exe -m my_art visit het-steen --dry-run
.\.venv\Scripts\python.exe -m my_art mock-image het-steen foreground
.\.venv\Scripts\python.exe -m my_art mock-image het-steen midground
```

Dans l'interface, les œuvres réelles sont proposées avant les exemples fictifs. Ouvrez **Tester les vues pédagogiques — sans appel API**, choisissez un plan puis cliquez sur **Simuler la génération de cette vue**. Le résultat utilise exactement le fichier fourni et reçoit un identifiant `mock-…`. La réponse simulée est enregistrée dans `output/museum/`.

## Parcours avec Nova et images simulées

1. Sélectionner Het Steen et demander une visite guidée ou poser une question.
2. Nova reçoit les deux textes, l'original facultatif et la description des vues disponibles.
3. Nova prépare des étapes sourcées et choisit `foreground` ou `midground` si une vue aide l'explication.
4. Après contrôle des citations, l'orchestrateur appelle `ImageProvider.generate(VisualRequest(...))`.
5. `MockImageProvider` simule la réponse de l'API avec `firstplan.png` ou `secondplan.png`.
6. L'interface affiche la vue auprès de l'explication, avec une mention de simulation.

Il n'y a **aucune requête HTTP de génération d'image**, aucun besoin de clé OpenAI et aucun coût de génération d'image. L'appel d'explication à Nova reste un appel Bedrock réel et facturable. La simulation ne crée ni ne modifie les pixels.

Les métadonnées indiquent la couverture de chaque vue. Le second plan fourni inclut aussi le lointain et le ciel ; le premier plan est une vue large, pas un détourage d'un personnage précis. Une demande de détail ou d'arrière-plan distinct non configuré renvoie `unavailable` : le texte et l'original restent utilisables. `overview` utilise l'original et `none` ne demande pas de vue.

Les résultats de visite incluent `visual_calls` et, pour chaque étape illustrée, un objet `visual` contenant la demande, le fichier choisi, son empreinte SHA-256, `simulated: true` et `external_api_calls: 0`. Plus tard, un autre fournisseur pourra implémenter `ImageProvider` sans changer la préparation du corpus.
