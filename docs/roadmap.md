# Vision et feuille de route

## Finalité

My-art vise une visite de musée compréhensible sans connaissances préalables : découvrir l’original, lire une explication simple, observer une zone pertinente, consulter les sources et approfondir à son rythme. Les vues pédagogiques complètent l’œuvre originale, qui reste accessible.

Le premier périmètre visé est de deux à trois œuvres réelles accompagnées de documents sélectionnés et relus. Aujourd’hui, le dépôt fournit Het Steen et deux corpus fictifs de test. Le fonctionnement livré est décrit dans l’[architecture actuelle](architecture.md) ; les éléments ci-dessous sont des objectifs, pas des fonctions déjà implémentées.

## Prochaines étapes

| Étape | Livrable attendu | Critère de validation |
| --- | --- | --- |
| Consolider le corpus | Deux à trois œuvres réelles avec images, notices et provenance. | Sources relues, informations manquantes explicites et conditions d’utilisation vérifiées. |
| Évaluer le parcours actuel | Questions de référence et bilan des réponses Nova. | Citations pertinentes, refus des informations absentes, coût et délai mesurés. |
| Tester la médiation | Explications simples et détaillées auprès des publics visés. | Les visiteurs peuvent reformuler les idées principales. |
| Vérifier l’accessibilité | Parcours clavier, lecteur d’écran, zoom, légendes et états de chargement. | Essais documentés ; aucune conformité supposée sur la seule présence de textes alternatifs. |
| Étendre la recherche si nécessaire | Fournisseur de contexte avec recherche textuelle ou vectorielle. | Provenance conservée et absence de mélange entre œuvres ; pertinence comparée au contexte direct. |
| Intégrer les vues si leur qualité le permet | Fournisseur visuel, validation humaine, cache et limites d’appels. | Fidélité à l’original, région pertinente et repli sur le texte en cas d’échec. |
| Préparer une mise à disposition | Gestion administrative, accès et politique de données. | Revue avant exposition à des visiteurs. |

La narration audio, les questions vocales, les langues supplémentaires et la reconnaissance d’une œuvre photographiée restent des pistes ultérieures.

## Principes à conserver

Les informations historiques et les interprétations doivent provenir de la documentation. Une observation visuelle ne démontre ni une identité, ni une date, ni une intention de l’artiste. Les contradictions et les absences de sources doivent rester visibles.

Les originaux et les variantes sont séparés. Une zone cachée reconstruite ne doit pas être présentée comme un détail authentique. Privilégier les vues préparées et relues, le recadrage ou le masquage lorsqu’ils suffisent ; une édition générative porte une mention de modification et demande une vérification visuelle.

L’orchestration doit rester bornée en appels, durée et coût. Un orchestrateur avec des outils spécialisés peut suffire : plusieurs agents ou plusieurs services ne sont pas un préalable. Toute recherche future devra gérer les versions des sources et l’invalidation des résultats dépendants.

## Évaluer le résultat

Préparer 10 à 15 questions par œuvre réelle, avec passages de référence, puis évaluer la fidélité des affirmations, la gestion de l’incertitude, les contradictions, l’isolation des œuvres et la pertinence des vues. Ajouter des questions hors sujet et des tentatives de détourner les consignes via les documents.

Compléter par des essais de compréhension, d’accessibilité et de robustesse en cas de source absente, vue indisponible ou service en erreur. Mesurer séparément les délais et coûts du texte et des images. Le [jeu de questions existant](../evaluation/README.md) constitue un premier support manuel, pas un résultat de qualité déjà obtenu.

Avant une utilisation publique, décider qui valide les textes et vues, quels publics participent aux essais, quelles données peuvent être envoyées aux fournisseurs, combien de temps conserver les traces et quels seuils de qualité, coût et latence accepter.
