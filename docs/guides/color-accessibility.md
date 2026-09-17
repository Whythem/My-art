# Contraste et aides à la distinction des couleurs

Dans **Contraste des images**, les options Normal, Élevé et Doux sont conservées.
Trois aides expérimentales sont proposées : Protanopie, Deutéranopie et Tritanopie.
Le curseur règle leur intensité de 0 à 100 %. Normal rétablit l’affichage original.
Les filtres s’appliquent à toutes les images d’œuvres affichées, y compris leurs
plans, mais pas au logo ni aux textes. Ils ne modifient ni les fichiers locaux,
ni le cache de génération, ni les images envoyées à Bedrock. Aucun appel IA n’est
nécessaire pour changer un filtre.

## Principe et limites

Les déficiences rouge–vert sont les plus fréquentes. La deutéranomalie est la
forme rouge–vert la plus courante ; la tritanopie appartient à une famille plus
rare. Les trois options sont des profils de recoloration, pas un diagnostic ni
un classement des trois formes les plus fréquentes.
[Référence : National Eye Institute](https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases/color-blindness/types-color-vision-deficiency).

Le filtre utilise les matrices de simulation de Machado, Oliveira et Fernandes
(2009), à sévérité maximale, pour estimer une différence chromatique. Les valeurs
numériques sont consultables dans la
[documentation source QGIS](https://api.qgis.org/api/4.0/qgsprevieweffect_8cpp_source.html).
Le modèle de simulation et la correction proposée sont deux choses différentes :
les matrices de simulation ne sont jamais affichées directement comme une aide.

La transformation appliquée est `I + intensité × R × (I − S)` en RGB linéaire.
`S` est la matrice de simulation et `R` une redistribution heuristique propre au
prototype : l’erreur rouge–vert est reportée sur le bleu ; l’erreur bleu–vert est
reportée sur l’opposition rouge–vert pour le profil tritanopie. Les matrices sont
normalisées pour conserver les gris neutres ; l’alpha reste inchangé. Le navigateur
applique une matrice SVG et borne les couleurs au gamut de l’écran.

La simulation scientifique ne valide pas médicalement cette redistribution.
Le bénéfice varie selon la personne, le tableau et l’écran ; certaines couleurs
peuvent devenir moins distinctes, notamment après écrêtage. Le curseur doit être
ajusté au confort de chacun. Les couleurs artistiques originales ne sont pas
préservées à l’écran pendant l’application du filtre.

Une évaluation avec des personnes concernées reste nécessaire. Les descriptions
textuelles, les positions des éléments et les vues séparées restent des aides
complémentaires : une information importante ne doit pas dépendre de la couleur
seule.
