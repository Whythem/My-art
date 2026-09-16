# Évaluer les explications

[bedrock-questions.json](bedrock-questions.json) contient des questions de référence pour les deux œuvres fictives de `examples/museum/`. Chaque entrée donne un identifiant d’œuvre, une question et un résultat attendu à apprécier humainement. Aucun lanceur automatique d’évaluation n’est implémenté.

## Utilisation

Installez le musée et configurez Bedrock selon le [guide](../docs/guides/bedrock.md). Préparez un catalogue de démonstration distinct :

```powershell
.\.venv\Scripts\python.exe -m my_art --data-dir data/demo init-demo
.\.venv\Scripts\python.exe -m my_art --data-dir data/demo ask demo-port "Que voit-on au premier plan ?" --text-only --dry-run
```

Le dry-run permet d’examiner le corpus sans appel. Retirer `--dry-run` déclenche la demande à Bedrock ; chaque question peut donc être facturée. Les résultats sont enregistrés dans `output/museum/`.

Pour chaque question, comparez la réponse à l’attente et aux passages cités. Relevez le modèle, la version du corpus, la qualité des citations, les affirmations non étayées, les refus appropriés, le délai mesuré et l’usage retourné. Une citation présente dans le corpus ne suffit pas à démontrer la justesse de l’explication.

Les tests automatisés dans `tests/` contrôlent les mécanismes avec des réponses simulées. Ce jeu sert à comparer les réponses réelles ; aucun score, coût ou délai réel n’est encore établi dans le dépôt. Ajoutez un jeu propre à chaque œuvre réelle avant de conclure sur la qualité du musée.
