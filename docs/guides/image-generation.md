# Tester les vues pédagogiques en Python

[Accueil](../../README.md) · [Architecture](../architecture.md)

Ce test envoie une image à l'API OpenAI Images et demande trois éditions distinctes : premier plan, arrière-plan visible et détail. Il n'implémente pas encore le RAG, la génération d'explications historiques ou l'orchestration agentique du musée.

## 1. Créer la clé API

La clé nécessaire est une **clé API OpenAI**, pas le mot de passe ChatGPT ni une clé AWS.

1. Connectez-vous à [OpenAI Platform — API keys](https://platform.openai.com/api-keys).
2. Sélectionnez le projet voulu, puis créez une clé secrète (**Create new secret key**).
3. Copiez-la dans votre configuration locale lors de sa création. Si une ancienne clé n'est plus accessible en clair, créez-en une nouvelle.
4. Vérifiez la [facturation API](https://platform.openai.com/settings/organization/billing/overview) et l'accès au modèle d'images. Une clé seule ne garantit pas un quota disponible.

**ChatGPT Plus ne paie pas les appels de ce script.** L'API dispose d'une facturation séparée à l'usage. Le tableau et les consignes sont envoyés à OpenAI lors d'une exécution réelle. Ne partagez pas votre clé dans la conversation, dans une capture ou dans Git.

## 2. Installer les dépendances

Python **3.10 ou ultérieur**. Dans PowerShell, depuis la racine du dépôt :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/imagegen.txt
Copy-Item .env.example .env
```

Copiez `.env.example` uniquement lors de la première configuration pour ne pas écraser un `.env` existant. Il n'est pas nécessaire d'activer l'environnement virtuel.

Ouvrez `.env` dans votre éditeur et renseignez :

```dotenv
OPENAI_API_KEY=votre_cle_api_openai
OPENAI_IMAGE_MODEL=gpt-image-2
```

Le script charge le `.env` situé à la racine du dépôt, même si vous le lancez depuis un autre dossier. Une variable d'environnement existante est prioritaire. `.env`, `.venv`, `input` et `output` sont ignorés par Git.

## 3. Fournir un tableau et simuler

Placez votre tableau, par exemple, dans `input/tableau.jpg` (créez le dossier `input`). Formats acceptés : PNG, JPEG, WEBP fixes, jusqu'à 20 Mio pour ce test.

```powershell
.\.venv\Scripts\python.exe -m my_art.generate_views "input\tableau.jpg" --dry-run
```

Ce mode vérifie le fichier et crée une copie de l'original et un `manifest.json` avec les consignes. Il ne nécessite pas de clé, n'envoie rien et ne génère aucune image. Vous pouvez l'exécuter avant de créer votre clé.

## 4. Générer une première vue

Pour évaluer la qualité sur un seul appel :

```powershell
.\.venv\Scripts\python.exe -m my_art.generate_views "input\tableau.jpg" --views premier_plan --quality low
```

Puis demander les trois vues, en précisant l'élément à isoler :

```powershell
.\.venv\Scripts\python.exe -m my_art.generate_views "input\tableau.jpg" --detail "le personnage assis à gauche" --quality medium
```

Sans `--detail`, la troisième vue cible « le sujet principal du tableau ». Choisissez un élément effectivement visible. Les trois éditions partent chacune de l'original pour éviter d'accumuler les modifications.

Autres options :

- `--views arriere_plan detail` : demander seulement certaines vues.
- `--output "mes-resultats"` : changer le dossier parent des sorties.
- `--model gpt-image-2` : remplacer la configuration du modèle pour cette exécution. Le modèle doit accepter l'API Images Edit et les paramètres employés.
- `--size auto` : laisser le modèle choisir la résolution ; aussi disponibles : `1024x1024`, `1536x1024`, `1024x1536`. Une taille explicite peut modifier le ratio par rapport à l'original.
- `--quality low|medium|high|auto` : régler la qualité. Le coût dépend notamment du modèle, de la résolution et de la qualité ; voir la [tarification API](https://developers.openai.com/api/docs/pricing).

## 5. Examiner les résultats

Chaque lancement crée un nouveau dossier sous `output/imagegen/` :

```text
20260916T120000Z-a1b2c3d4/
├── original.jpg
├── premier_plan.png
├── arriere_plan.png
├── detail.png
└── manifest.json
```

Seules les vues sélectionnées et réussies sont présentes. Le manifest conserve les consignes, le modèle, les paramètres, l'empreinte de l'original, l'état de chaque vue et l'usage renvoyé par l'API lorsqu'il est disponible. Il ne contient pas la clé. L'état `generated_unreviewed` signifie que le fichier a été produit, **pas que sa fidélité a été validée**.

Les régions exclues sont demandées en **gris clair uni** : l'arrière-plan caché derrière un personnage ne doit pas être inventé. Aucun texte n'est demandé dans les images. Les légendes et explications du musée seront gérées séparément.

Vérifiez visuellement les contours, les couleurs, les visages, l'absence d'éléments ajoutés et la correspondance de la région conservée à la consigne. Un modèle génératif peut modifier des détails malgré les instructions. Pour garantir la conservation exacte des pixels, il faudra un traitement déterministe fondé sur des masques de segmentation validés.

## 6. Erreurs et relance

- **401** : clé incorrecte ou expirée.
- **403 / 404** : vérifier l'accès au modèle, les permissions du projet et l'identifiant configuré ; une vérification d'organisation peut être requise selon le modèle.
- **429** : vérifier les crédits, le quota et les limites de débit API.
- **400** : vérifier le format, les paramètres et la consigne ; le service peut aussi refuser une demande.
- **Délai dépassé ou interruption réseau** : vérifier l'usage avant de relancer, car une requête peut avoir été traitée sans que sa réponse soit arrivée.

Le script s'arrête au premier échec et conserve les vues déjà reçues. Il ne réessaie pas automatiquement. Une relance est une nouvelle génération facturable, dans un nouveau dossier ; utilisez `--views` pour ne redemander que les vues manquantes.

## 7. Vérification locale sans facturation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_generate_views.py" -v
```

Les tests emploient un transport HTTP simulé, sans clé réelle et sans appel réseau. Ils vérifient notamment que chaque édition reçoit l'original, que les sorties sont enregistrées et que les erreurs conservent les résultats partiels. Ils ne mesurent pas la qualité artistique ni l'accès réel de votre compte.

Références : [premier appel et clé API](https://developers.openai.com/api/docs/quickstart), [génération et édition d'images](https://developers.openai.com/api/docs/guides/image-generation), [modèle GPT Image 2](https://developers.openai.com/api/docs/models/gpt-image-2).
