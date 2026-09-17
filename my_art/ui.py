"""Interface locale de test. Aucune requête AWS avant soumission explicite."""

from dataclasses import replace
import json

import streamlit as st

from my_art.bedrock import ModelError, SYSTEM
from my_art.runtime import make_service, save_result
from my_art.config import MODELS, Settings
from my_art.corpus import Catalog
from my_art.visuals import asset_path
from my_art.paths import ROOT
from my_art.discovery import catalog_snapshot


@st.fragment(run_every=3)
def watch_catalog(data_dir, snapshot):
    if catalog_snapshot(data_dir) != snapshot:
        st.rerun()


def show_visual(catalog, visual, artwork_id):
    if visual["status"] != "ready":
        st.info(visual["message"])
        return
    try:
        path = asset_path(catalog, artwork_id, visual["file"])
        st.image(str(path), caption=f"{visual['label']} — vue pédagogique préparée")
        st.text(visual["description"])
        st.caption("Génération simulée : image déjà fournie, aucun appel API d'images.")
    except (ValueError, OSError):
        st.info("Cette vue n'est plus disponible. Revenez à la présentation générale pour consulter l'original.")


def main():
    logo_path = ROOT / "data" / "logo" / "logo.png"
    st.set_page_config(
        page_title="Augmented Art for Accessibility",
        page_icon=str(logo_path),
        layout="centered",
    )

    col_logo, col_title = st.columns([1, 5])
    with col_logo:
        st.image(str(logo_path), width=90)
    with col_title:
        st.title("Augmented Art for Accessibility")
    st.write("Explorer une œuvre, une explication à la fois.")
    st.caption("Prototype local : les réponses reposent sur la documentation de l'œuvre sélectionnée.")

    try:
        settings = Settings.from_env()
        snapshot = catalog_snapshot(settings.data_dir)
        watch_catalog(settings.data_dir, snapshot)
        catalog = Catalog(settings.data_dir)
        artworks = sorted(catalog.list(), key=lambda art: (art.demo, art.title))
    except (ValueError, OSError) as exc:
        st.error(str(exc) if isinstance(exc, ValueError) else "Impossible de lire le catalogue local.")
        st.stop()

    if not artworks:
        st.info("Le catalogue est vide. Ajoutez une œuvre selon le guide docs/guides/bedrock.md.")
        st.code("python -m my_art init-demo", language="shell")
        st.stop()

    with st.sidebar:
        contrast = st.selectbox("Contraste des images", ["Normal", "Élevé (high contrast)", "Doux (low contrast)"])
        st.caption("Choisissez le rendu le plus confortable. L’original reste inchangé ; ce réglage ne corrige pas toutes les formes de daltonisme.")
        st.header("Configuration du test")
        model_id = st.selectbox("Modèle Bedrock", list(MODELS), index=list(MODELS).index(settings.model_id))
        st.caption(f"Région : {settings.region}")
        st.caption("Un appel Bedrock maximum par demande. Les appels d'images sont simulés avec les vues fournies. Aucun appel OpenAI ou audio.")
        st.caption("L'aperçu du contexte fonctionne sans identifiants AWS.")

    image_contrast = {"Normal": "1", "Élevé (high contrast)": "1.6", "Doux (low contrast)": "0.75"}[contrast]
    st.markdown(f"<style>[data-testid='stImage'] img {{filter: contrast({image_contrast});}}</style>", unsafe_allow_html=True)
    settings = replace(settings, model_id=model_id)
    artwork_id = st.selectbox("Œuvre", [a.id for a in artworks],
                             format_func=lambda value: next(a.title for a in artworks if a.id == value))
    artwork = next(a for a in artworks if a.id == artwork_id)
    st.subheader(artwork.title)
    st.write(artwork.artist)
    if artwork.demo:
        st.warning("Œuvre fictive : ce corpus sert uniquement à tester l'application.")
    saved = st.session_state.get("museum_result")
    current_result = saved["result"] if saved and saved["result"]["artwork"]["id"] == artwork_id else None
    try:
        image = catalog.image_bytes(artwork)
        if image and not (current_result and current_result.get("visit", {}).get("status") == "answered"):
            st.image(image, caption=artwork.image_alt or "Image de référence de l'œuvre")
            if artwork.image_alt:
                st.write(f"Description de l'image : {artwork.image_alt}")
        elif not image:
            st.info("Aucune image de référence identifiée. Ajoutez une image nommée original.jpg "
                    "ou portant l'identifiant de l'œuvre dans son dossier. S'il y a plusieurs "
                    "originaux possibles, précisez le champ image dans metadata.json.")
    except (ValueError, OSError) as exc:
        st.error(str(exc) if isinstance(exc, ValueError) else "Impossible de lire l'image locale.")
        st.stop()

    uploads = st.file_uploader("Ajouter des documents pour cette œuvre (facultatif)", type=["txt"],
                               accept_multiple_files=True, key=f"documents_{artwork_id}")
    st.caption("TXT UTF-8 : 10 fichiers maximum, 1 Mo chacun. Ces ajouts servent uniquement aux demandes de cette œuvre dans cette session. Leur texte figure dans le résultat téléchargeable et enregistré localement.")
    with st.form("visit_request"):
        mode_label = st.radio("Que souhaitez-vous faire ?", ["Poser une question", "Suivre une visite guidée"], index=1)
        question = st.text_area("Votre question (facultative pour la visite guidée)", max_chars=2000,
                                placeholder="Que représente le premier plan ?")
        level_label = st.radio("Niveau d'explication", ["Simple", "Détaillé"], horizontal=True)
        include_image = st.checkbox("Joindre les images à l’analyse (tous les plans en mode question)", value=bool(image or artwork.views) and MODELS[model_id],
                                    disabled=not (image or artwork.views) or not MODELS[model_id],
                                    key=f"attach_{artwork_id}_{model_id}_{bool(image)}")
        preview = st.form_submit_button("Vérifier le contexte — sans appel API")
        submit = st.form_submit_button("Demander l'explication — appel Bedrock")

    if mode_label == "Suivre une visite guidée":
        with st.sidebar.expander("Consigne de visite guidée"):
            st.text(SYSTEM)

    if preview or submit:
        st.session_state.pop("museum_result", None)
        try:
            service = make_service(settings)
            prepared = service.prepare(artwork_id, question,
                                       "ask" if mode_label == "Poser une question" else "visit",
                                       "simple" if level_label == "Simple" else "detaille",
                                       include_image and MODELS[model_id],
                                       documents=[(file.name, file.getvalue()) for file in uploads])
            if preview:
                result = {**prepared.preview(), "status": "dry_run", "calls": 0,
                          "model": model_id, "region": settings.region}
            else:
                with st.spinner("Préparation de l'explication à partir des sources…"):
                    result = service.run(prepared)
            path = save_result(result)
            st.session_state["museum_result"] = {"result": result, "path": str(path)}
            st.rerun()
        except (ValueError, ModelError, OSError) as exc:
            st.error(str(exc) if isinstance(exc, (ValueError, ModelError)) else "Erreur de fichier local.")

    with st.container():
        saved = st.session_state.get("museum_result")
        if saved and saved["result"]["artwork"]["id"] == artwork_id:
            result = saved["result"]
            st.divider()
            st.caption(f"Résultat de la dernière demande · {result['model']} · niveau {result['level']}")
            source_map = {s["id"]: s for s in result["context"]["sources"]}
            if result.get("status") == "dry_run":
                st.success("Contexte préparé localement. Aucun appel API effectué.")
                st.write(f"{len(source_map)} passages ; {len(result.get('attached_images', []))} image(s) jointe(s).")
            else:
                st.info(result["message"])
                for index, step in enumerate(result["visit"]["steps"], 1):
                    st.subheader(f"{index}. {step['title']}" if result["mode"] == "visit" else step["title"])
                    if step.get("visual"):
                        show_visual(catalog, step["visual"], artwork_id)
                    elif step["visual_focus"] == "overview" and image:
                        st.image(image, caption=artwork.image_alt or "Tableau original")
                    st.caption("Selon la documentation" if step["basis"] == "document" else "Observation visuelle de l'IA")
                    st.text(step["text"])
                    for evidence in step["evidence"]:
                        source = source_map[evidence["source_id"]]
                        with st.expander(f"Source : {source['document']} — {source['location']}"):
                            st.text(evidence["quote"])
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
