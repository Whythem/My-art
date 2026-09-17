"""Interface locale de test pour configurer un profil et interroger Bedrock."""

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


DISABILITY_OPTIONS = [
    ("daltonisme", "Daltonisme"),
    ("trisomie", "Trisomie"),
    ("cecite", "Cécité"),
]

DEFAULT_PROFILE = {
    "contrast": "Normal",
    "level": "Simple",
    "show_planes": True,
    "soundscape": False,
}

PROFILE_PRESETS = {
    "daltonisme": {"contrast": "Élevé (high contrast)", "level": "Détaillé", "show_planes": True},
    "trisomie": {"contrast": "Doux (low contrast)", "level": "Simple", "show_planes": True},
    "cecite": {"contrast": "Normal", "level": "Détaillé", "show_planes": False, "soundscape": True},
}

CONTRAST_VALUES = {
    "Normal": "1",
    "Élevé (high contrast)": "1.6",
    "Doux (low contrast)": "0.75",
}


def ensure_profile_state():
    for key, value in DEFAULT_PROFILE.items():
        st.session_state.setdefault(f"profile_{key}", value)
    st.session_state.setdefault("profile_disability", DISABILITY_OPTIONS[0][0])
    st.session_state.setdefault("profile_disability_previous", None)
    st.session_state.setdefault("profile_saved", False)


def selected_disability():
    return st.session_state["profile_disability"]


def apply_disability_preset(disability):
    profile = DEFAULT_PROFILE.copy()
    profile.update(PROFILE_PRESETS[disability])
    for key, value in profile.items():
        st.session_state[f"profile_{key}"] = value


def current_profile():
    return {
        "disability": selected_disability(),
        "contrast": st.session_state["profile_contrast"],
        "level": st.session_state["profile_level"],
        "show_planes": st.session_state["profile_show_planes"],
        "soundscape": st.session_state["profile_soundscape"],
    }


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
    ensure_profile_state()

    col_logo, col_title = st.columns([1, 5], vertical_alignment="center")
    with col_logo:
        st.image(str(logo_path), width=110)
    with col_title:
        st.title("Mon profil")
        st.caption("Configurez les préférences que l'agent appliquera ensuite aux œuvres sélectionnées.")

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
        with st.expander("Consigne de médiation appliquée automatiquement"):
            st.text(SYSTEM)
        st.header("Configuration du test")
        model_id = st.selectbox("Modèle Bedrock", list(MODELS), index=list(MODELS).index(settings.model_id))
        st.caption(f"Région : {settings.region}")
        st.caption("Un appel Bedrock maximum par demande. Les appels d'images sont simulés avec les vues fournies. Aucun appel OpenAI ou audio.")
        st.caption("L'ambiance sonore est enregistrée dans le profil mais n'est pas encore reliée au code.")

    with st.expander("Configurer mon profil", expanded=not st.session_state["profile_saved"]):
        st.radio(
            "Type de handicap",
            [key for key, _label in DISABILITY_OPTIONS],
            format_func=lambda value: next(label for key, label in DISABILITY_OPTIONS if key == value),
            horizontal=True,
            key="profile_disability",
        )

        disability = selected_disability()
        if disability != st.session_state["profile_disability_previous"]:
            apply_disability_preset(disability)
            st.session_state["profile_disability_previous"] = disability

        st.selectbox("Niveau de contraste", list(CONTRAST_VALUES), key="profile_contrast")
        st.radio("Niveau de détail des explications", ["Simple", "Détaillé"], horizontal=True, key="profile_level")
        st.checkbox("Voir les différents plans", key="profile_show_planes")
        st.checkbox("Ambiance sonore", key="profile_soundscape")

        if st.button("Valider mon profil", type="primary"):
            st.session_state["profile_saved"] = True
            st.session_state.pop("museum_result", None)
            st.session_state.pop("museum_request_key", None)
            st.rerun()

    if not st.session_state["profile_saved"]:
        st.info("Validez le profil pour ouvrir la sélection des œuvres.")
        st.stop()

    profile = current_profile()
    st.success("Profil enregistré pour cette session.")

    image_contrast = CONTRAST_VALUES[profile["contrast"]]
    st.markdown(f"<style>[data-testid='stImage'] img {{filter: contrast({image_contrast});}}</style>", unsafe_allow_html=True)
    settings = replace(settings, model_id=model_id)
    st.subheader("Choisir une œuvre")
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

    result_container = st.container()

    request_key = json.dumps({
        "artwork_id": artwork_id,
        "model_id": model_id,
        "contrast": profile["contrast"],
        "level": profile["level"],
        "disability": profile["disability"],
        "show_planes": profile["show_planes"],
        "soundscape": profile["soundscape"],
        "image": bool(image),
    }, sort_keys=True)
    if st.session_state.get("museum_request_key") != request_key:
        st.session_state.pop("museum_result", None)
        try:
            service = make_service(settings)
            prepared = service.prepare(
                artwork_id,
                "",
                "visit",
                "simple" if profile["level"] == "Simple" else "detaille",
                bool(image) and MODELS[model_id],
            )
            with st.spinner("Préparation de l'explication à partir des sources…"):
                result = service.run(prepared)
            path = save_result(result)
            st.session_state["museum_result"] = {"result": result, "path": str(path)}
            st.session_state["museum_request_key"] = request_key
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
                    show_step_visual = profile["show_planes"] or step["visual_focus"] == "overview"
                    if show_step_visual and step.get("visual"):
                        show_visual(catalog, step["visual"], artwork_id)
                    elif show_step_visual and step["visual_focus"] == "overview" and image:
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
