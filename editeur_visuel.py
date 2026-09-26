import os
import io
import requests
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

load_dotenv()
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


@st.cache_data(ttl=600, show_spinner=False)
def _telecharger_fichier_modele(url):
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    if not response.content:
        raise ValueError("Le serveur a renvoyé un fichier vide.")
    return response.content


def charger_fichier(entreprise, modele, fichier):
    url = f"{API_URL}/modeles/{entreprise}/{modele}/fichier/{fichier}"
    try:
        return _telecharger_fichier_modele(url)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "inconnu"
        st.error(f"Fichier {fichier} indisponible (HTTP {status}) : {url}")
        return None
    except (requests.RequestException, ValueError) as exc:
        st.error(f"Échec du chargement de {fichier} : {exc}")
        return None
    except Exception as exc:
        st.error(f"Erreur de chargement de {fichier} : {exc}")
        return None

def afficher_editeur(entreprise, modele, mode='nouveau', config=None):
    modification = mode == 'modifier'
    fichiers_modifies = {}

    if modification:
        st.subheader("Modification du modèle")

        base_bytes = charger_fichier(entreprise, modele, "base_reference")
        overlay_bytes = charger_fichier(entreprise, modele, "calque_fixe")
        fond_bytes = charger_fichier(entreprise, modele, "fond_defaut")

        if not base_bytes or not overlay_bytes or not fond_bytes:
            st.error("Impossible de charger les fichiers du modèle.")
            return None

        try:
            base = Image.open(io.BytesIO(base_bytes)).convert("RGBA")
            ov = Image.open(io.BytesIO(overlay_bytes)).convert("RGBA")
            fd = Image.open(io.BytesIO(fond_bytes)).convert("RGBA")
        except Exception as exc:
            st.error(f"Les fichiers du modèle ne sont pas des images valides : {exc}")
            return None

        st.write("### Remplacer un fichier")

        nouveau_base = st.file_uploader(
            "Nouvelle base de référence",
            type=["png", "jpg", "jpeg"],
            key=f"base_mod_{entreprise}_{modele}"
        )

        nouveau_overlay = st.file_uploader(
            "Nouveau calque fixe",
            type=["png"],
            key=f"overlay_mod_{entreprise}_{modele}"
        )

        nouveau_fond = st.file_uploader(
            "Nouveau fond",
            type=["png", "jpg", "jpeg"],
            key=f"fond_mod_{entreprise}_{modele}"
        )

        if nouveau_base:
            base = Image.open(io.BytesIO(nouveau_base.getvalue())).convert("RGBA")
            base_bytes = nouveau_base.getvalue()
            fichiers_modifies["base_reference"] = ("base.png", base_bytes, "image/png")

        if nouveau_overlay:
            ov = Image.open(io.BytesIO(nouveau_overlay.getvalue())).convert("RGBA")
            overlay_bytes = nouveau_overlay.getvalue()
            fichiers_modifies["calque_fixe"] = ("overlay.png", overlay_bytes, "image/png")

        if nouveau_fond:
            fd = Image.open(io.BytesIO(nouveau_fond.getvalue())).convert("RGBA")
            fond_bytes = nouveau_fond.getvalue()
            fichiers_modifies["fond_defaut"] = ("fond.png", fond_bytes, "image/png")

        overlay = ov
        fond = fd

    else:
        st.subheader("Configuration du nouveau modèle")

        base = st.file_uploader(
            "1️⃣ Base de référence — sert uniquement à mesurer",
            type=["png", "jpg", "jpeg"],
            key=f"base_{entreprise}_{modele}"
        )

        overlay = st.file_uploader(
            "2️⃣ Calque fixe transparent",
            type=["png"],
            key=f"overlay_{entreprise}_{modele}"
        )

        fond = st.file_uploader(
            "3️⃣ Fond par défaut",
            type=["png", "jpg", "jpeg"],
            key=f"fond_{entreprise}_{modele}"
        )

        if not base or not overlay or not fond:
            st.info("Charge les 3 fichiers : base, calque fixe transparent et fond par défaut.")
            return None

    if not base or not overlay or not fond:
        st.info("Les 3 fichiers du modèle sont nécessaires.")
        return None

    if modification:
        base_source = io.BytesIO(base_bytes)
        overlay_source = io.BytesIO(overlay_bytes)
        fond_source = io.BytesIO(fond_bytes)
    else:
        base_bytes = base.getvalue()
        overlay_bytes = overlay.getvalue()
        fond_bytes = fond.getvalue()
        base_source = base
        overlay_source = overlay
        fond_source = fond

    image = Image.open(base_source).convert("RGBA")
    ov = Image.open(overlay_source).convert("RGBA")
    fd = Image.open(fond_source).convert("RGBA")

    if image.size != ov.size:
        st.error("La base de référence et le calque fixe doivent avoir exactement les mêmes dimensions.")
        return None

    if ov.getchannel("A").getextrema() == (255, 255):
        st.warning("Attention : le calque fixe ne contient aucune zone transparente.")

    st.write(f"**Dimensions finales :** {image.width} × {image.height}")

    width = min(image.width, 900)
    height = int(image.height * width / image.width)

    initial_objects = []
    if modification:
        zones_existantes = (config or {}).get("zones_modifiables", {})
        for nom, zone in zones_existantes.items():
            scale = width / image.width
            x = round(zone.get("x", 0) * scale)
            y = round(zone.get("y", 0) * scale)
            zone_width = round(zone.get("largeur", 0) * scale)
            zone_height = round(zone.get("hauteur", 0) * scale)
            initial_objects.append({
                "type": "LabeledRect",
                "label": nom,
                "left": x,
                "top": y,
                "originX": "left",
                "originY": "top",
                "width": zone_width,
                "height": zone_height,
                "scaleX": 1,
                "scaleY": 1,
                "angle": 0,
                "stroke": "#ff0000",
                "strokeWidth": 2,
                "fill": "rgba(255, 0, 0, 0.15)",
                "lockRotation": True,
                "strokeUniform": True
            })

    outil = st.radio(
        "Outil",
        ["✋ Déplacer/redimensionner", "➕ Ajouter une zone"],
        horizontal=True,
        key=f"outil_{entreprise}_{modele}"
    )
    canvas = st_canvas(
        fill_color="rgba(255, 0, 0, 0.15)",
        stroke_width=2,
        stroke_color="#ff0000",
        background_image=image,
        update_streamlit=True,
        height=height,
        width=width,
        drawing_mode="rect",
        initial_drawing={"version": "5.2.4", "objects": initial_objects} if initial_objects else None,
        key=f"canvas_{entreprise}_{modele}_{modification}"
    )

    objects = (canvas.json_data or {}).get("objects", [])

    if not objects and not modification:
        st.info("Dessine au moins une zone sur le modèle.")
        return None

    zones = {}
    factor = image.width / width

    for i, obj in enumerate(objects):
        label = obj.get("label", "")
        left = float(obj.get("left", 0))
        top = float(obj.get("top", 0))
        w = float(obj.get("width", 0)) * float(obj.get("scaleX", 1))
        h = float(obj.get("height", 0)) * float(obj.get("scaleY", 1))

        x = max(0, round(left * factor))
        y = max(0, round(top * factor))

        ww = min(round(w * factor), image.width - x)
        hh = min(round(h * factor), image.height - y)

        zone_key = label.strip() or f"nouvelle_{i}"
        c1, c2 = st.columns([2, 1])

        with c1:
            name = st.text_input(
                f"Nom de la zone {i + 1}",
                key=f"name_{entreprise}_{modele}_{zone_key}",
                value=label,
                placeholder="Ex: titre, prix, image, description..."
            )

        with c2:
            zone_existante = (config or {}).get("zones_modifiables", {}).get(label, {})
            type_options = ["texte", "image"]
            typ = st.selectbox(
                "Type",
                type_options,
                index=type_options.index(zone_existante.get("type", "texte"))
                if zone_existante.get("type", "texte") in type_options else 0,
                key=f"type_{entreprise}_{modele}_{zone_key}_v2"
            )

        if not name.strip():
            continue

        if typ == "texte":
            c1, c2, c3 = st.columns([2, 1, 1])

            with c1:
                font = st.selectbox(
                    "Police",
                    [
                        "Inter",
                        "Roboto",
                        "Lato",
                        "Open Sans",
                        "Montserrat",
                        "Poppins"
                    ],
                    key=f"font_{entreprise}_{modele}_{i}"
                )

            with c2:
                weight = st.selectbox(
                    "Graisse",
                    [400, 500, 600, 700, 800, 900],
                    index=3,
                    format_func=lambda x: {
                        400: "Regular",
                        500: "Medium",
                        600: "SemiBold",
                        700: "Bold",
                        800: "ExtraBold",
                        900: "Black"
                    }[x],
                    key=f"weight_{entreprise}_{modele}_{i}"
                )

            with c3:
                size = st.number_input(
                     "Taille", 1, 500, 50, 1, 
                     key=f"size_{entreprise}_{modele}_{i}" )
     
            style = st.selectbox(
                    "Style",
                    ["normal", "italic"],
                    format_func=lambda x: "Normal" if x == "normal" else "Italique",
                    key=f"style_{entreprise}_{modele}_{i}"
                )

            alignement = st.selectbox(
                "Alignement",
                ["left", "center", "right"],
                index=1,
                key=f"alignement_{entreprise}_{modele}_{i}"
            )

            zones[name.strip()] = {
                "type": "texte",
                "x": x,
                "largeur": ww,
                "hauteur": hh,
                "y": y,
                "font": font,
                "weight": int(weight),
                "style": style,
                "size": int(size),
                "alignement": alignement
            }

        else:
            zones[name.strip()] = {
                "type": "image",
                "x": x,
                "y": y,
                "largeur": ww,
                "hauteur": hh
            }

    if not zones:
        return None

    st.write("### Aperçu des zones")
    st.json(zones)

    return {
        "entreprise": entreprise,
        "modele": modele,
        "config": {
            "zones_modifiables": zones
        },
        "_files": {
            "base": base_bytes,
            "overlay": overlay_bytes,
            "fond": fond_bytes
        },
        "_changed_files": fichiers_modifies
    }