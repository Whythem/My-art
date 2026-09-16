"""Interface locale de test. Aucune requête AWS avant soumission explicite."""

from dataclasses import replace
import json

import streamlit as st

from my_art.bedrock import ModelError
from my_art.cli import make_service, save_result
from my_art.config import MODELS, Settings
from my_art.corpus import Catalog
from my_art.visuals import MockImageProvider, VisualRequest, asset_path


def show_visual(visual, artwork_id):
    if visual["status"] != "ready":
        st.info(visual["message"])
        return
    try:
        path = asset_path(catalog, artwork_id, visual["file"])
        st.image(str(path), caption=f"{visual['label']} — vue pédagogique préparée")
        st.text(visual["description"])
        st.caption("Génération simulée : image déjà fournie, aucun appel API d'images.")
    except (ValueError, OSError):
        st.info("Cette vue n'est plus disponible. L'image originale reste visible en haut de page.")

st.set_page_config(page_title="My-art — Parcours documentaire", page_icon="🎨", layout="centered")
st.title("My-art")
st.write("Explorer une œuvre, une explication à la fois.")
st.caption("Prototype local : les réponses reposent sur la documentation de l'œuvre sélectionnée.")

try:
    settings = Settings.from_env()
    catalog = Catalog(settings.data_dir)
    artworks = sorted(catalog.list(), key=lambda art: (art.demo, art.title))
except (ValueError, OSError) as exc:
    st.error(str(exc) if isinstance(exc, ValueError) else "Impossible de lire le catalogue local.")
    st.stop()

if not artworks:
    st.info("Le catalogue est vide. Ajoutez une œuvre selon le guide docs/bedrock-poc.md.")
    st.code("python -m my_art init-demo", language="shell")
    st.stop()

with st.sidebar:
    st.header("Configuration du test")
    model_id = st.selectbox("Modèle Bedrock", list(MODELS), index=list(MODELS).index(settings.model_id))
    st.caption(f"Région : {settings.region}")
    st.caption("Un appel Bedrock maximum par demande. Les appels d'images sont simulés avec les vues fournies. Aucun appel OpenAI ou audio.")
    st.caption("L'aperçu du contexte fonctionne sans identifiants AWS.")

settings = replace(settings, model_id=model_id)
artwork_id = st.selectbox("Œuvre", [a.id for a in artworks],
                         format_func=lambda value: next(a.title for a in artworks if a.id == value))
artwork = next(a for a in artworks if a.id == artwork_id)
st.subheader(artwork.title)
st.write(artwork.artist)
if artwork.demo:
    st.warning("Œuvre fictive : ce corpus sert uniquement à tester l'application.")
try:
    image = catalog.image_bytes(artwork)
    if image:
        st.image(image, caption=artwork.image_alt or "Image de référence de l'œuvre")
        if artwork.image_alt:
            st.write(f"Description de l'image : {artwork.image_alt}")
    else:
        st.info("Aucune image de référence ajoutée. Le parcours documentaire reste disponible.")
except (ValueError, OSError) as exc:
    st.error(str(exc) if isinstance(exc, ValueError) else "Impossible de lire l'image locale.")
    st.stop()

if artwork.views:
    with st.expander("Tester les vues pédagogiques — sans appel API"):
        focus = st.selectbox("Vue à demander", list(artwork.views),
                             format_func=lambda value: artwork.views[value].label,
                             key=f"visual_choice_{artwork_id}")
        if st.button("Simuler la génération de cette vue"):
            visual = MockImageProvider(catalog).generate(VisualRequest(
                artwork_id, focus, artwork.views[focus].description))
            path = save_result(visual)
            st.session_state["mock_visual"] = {"artwork_id": artwork_id, "result": visual}
        stored_visual = st.session_state.get("mock_visual")
        if stored_visual and stored_visual["artwork_id"] == artwork_id:
            show_visual(stored_visual["result"], artwork_id)
            st.caption(f"Identifiant de l'appel simulé : {stored_visual['result']['request_id']}")

with st.form("visit_request"):
    mode_label = st.radio("Que souhaitez-vous faire ?", ["Poser une question", "Suivre une visite guidée"])
    question = st.text_area("Votre question (facultative pour la visite guidée)", max_chars=2000,
                            placeholder="Que représente le premier plan ?")
    level_label = st.radio("Niveau d'explication", ["Simple", "Détaillé"], horizontal=True)
    include_image = st.checkbox("Joindre le tableau à l'analyse", value=bool(image) and MODELS[model_id],
                                disabled=not image or not MODELS[model_id],
                                key=f"attach_{artwork_id}_{model_id}")
    preview = st.form_submit_button("Vérifier le contexte — sans appel API")
    submit = st.form_submit_button("Demander l'explication — appel Bedrock")

if preview or submit:
    st.session_state.pop("museum_result", None)
    try:
        service = make_service(settings)
        prepared = service.prepare(artwork_id, question,
                                   "ask" if mode_label == "Poser une question" else "visit",
                                   "simple" if level_label == "Simple" else "detaille",
                                   include_image and MODELS[model_id])
        if preview:
            result = {**prepared.preview(), "status": "dry_run", "calls": 0,
                      "model": model_id, "region": settings.region}
        else:
            with st.spinner("Préparation de l'explication à partir des sources…"):
                result = service.run(prepared)
        path = save_result(result)
        st.session_state["museum_result"] = {"result": result, "path": str(path)}
    except (ValueError, ModelError, OSError) as exc:
        st.error(str(exc) if isinstance(exc, (ValueError, ModelError)) else "Erreur de fichier local.")

saved = st.session_state.get("museum_result")
if saved and saved["result"]["artwork"]["id"] == artwork_id:
    result = saved["result"]
    st.divider()
    st.caption(f"Résultat de la dernière demande · {result['model']} · niveau {result['level']}")
    source_map = {s["id"]: s for s in result["context"]["sources"]}
    if result.get("status") == "dry_run":
        st.success("Contexte préparé localement. Aucun appel API effectué.")
        st.write(f"{len(source_map)} passages ; image jointe : {'oui' if result['image_attached'] else 'non'}.")
    else:
        st.info(result["message"])
        for index, step in enumerate(result["visit"]["steps"], 1):
            st.subheader(f"{index}. {step['title']}")
            st.caption("Selon la documentation" if step["basis"] == "document" else "Observation visuelle de l'IA")
            st.text(step["text"])
            for evidence in step["evidence"]:
                source = source_map[evidence["source_id"]]
                with st.expander(f"Source : {source['document']} — {source['location']}"):
                    st.text(evidence["quote"])
            if step.get("visual"):
                show_visual(step["visual"], artwork_id)
            elif step["visual_focus"] == "overview":
                st.caption("Vue d'ensemble : consulter l'image originale en haut de page.")
            elif step["visual_focus"] != "none":
                st.caption("Zone suggérée pour une future vue pédagogique (image non générée)")
                st.text(step["visual_target"])
        st.caption("Les références sont contrôlées automatiquement ; leur pertinence et les explications restent à relire.")
    with st.expander("Documentation utilisée et détails du test"):
        for source in source_map.values():
            st.write(f"{source['document']} — {source['location']}")
            st.text(source["text"])
        st.write(f"Appels : {result['calls']}")
        st.write(f"Appels d'images simulés : {len(result.get('visual_calls', []))}")
        st.json(result.get("usage", {}))
        st.caption(f"Version du corpus : {result['context']['version']}")
        st.download_button("Télécharger le résultat JSON", json.dumps(result, ensure_ascii=False, indent=2),
                           file_name="visite.json", mime="application/json")
