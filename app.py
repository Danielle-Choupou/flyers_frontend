import io,json,os,requests,hashlib,uuid
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import streamlit as st
from PIL import Image, ImageOps, ImageFilter
from streamlit_cropper import st_cropper
from editeur_visuel import afficher_editeur

load_dotenv()
try:
    API_URL=st.secrets.get('API_URL',os.getenv('API_URL','http://127.0.0.1:8000')).rstrip('/')
except (FileNotFoundError, AttributeError):
    API_URL=os.getenv('API_URL','http://127.0.0.1:8000').rstrip('/')
st.set_page_config(page_title='Générateur Flyers Pro',layout='wide',page_icon='✨')
st.title('✨ Visual Copilot AI')
st.caption('Générateur de flyers automatisé')


for key,default in {'image_valide_bytes':None,'img_page':1,'flyer_genere':None,'flyer_genere_signature':None,'caption_adaptations':{},'texte_accompagnement_source':'','derniere_data_flyer':None,'image_croppee_bytes':None,'modeles_details': {},'preview_flyer_bytes':None,'preview_flyer_signature':None,'preview_flyer_error_signature':None,'preview_flyer_error':None,'image_model_context':None}.items():
    if key not in st.session_state: st.session_state[key]=default

def _api_error_message(response):
    try:
        detail_value=response.json().get('detail')
        if detail_value:
            return str(detail_value)
    except (ValueError, AttributeError):
        pass
    return response.text[:500] if response is not None else 'Réponse indisponible'

@st.cache_data(ttl=60, show_spinner=False)
def _api_get_json(path,_request_id):
    response=requests.get(
        f'{API_URL}{path}',
        headers={'X-Request-ID':_request_id},
        timeout=20
    )
    response.raise_for_status()
    return response.json()

def api_get(path):
    request_id=uuid.uuid4().hex
    try:
        return _api_get_json(path,request_id)
    except requests.Timeout:
        st.error(f"Délai dépassé pendant la lecture de {path}. Référence : {request_id}")
        return None
    except requests.RequestException as exc:
        response=getattr(exc,'response',None)
        st.error(f"Lecture de {path} échouée : {_api_error_message(response)}. Référence : {request_id}")
        return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_history_images(page):
    response = requests.get(f'{API_URL}/historique', params={'page': page}, timeout=30)
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=600, show_spinner=False)
def fetch_history_image(path):
    response = requests.get(f'{API_URL}{path}', timeout=30)
    response.raise_for_status()
    return response.content

@st.cache_data(ttl=600, show_spinner=False)
def fetch_history_thumbnail(url):
    response=requests.get(url,timeout=30)
    response.raise_for_status()
    return response.content

def detail(r):
    try:return r.json().get('detail',r.text)
    except:return r.text

def enregistrer_image_historique(image_bytes):
    if not image_bytes:
        return

    try:
        r=requests.post(
            f'{API_URL}/historique',
            files={'image':('image.png',image_bytes,'image/png')},
            timeout=20
        )

        if not r.ok:
            st.error(f'Erreur historique : {r.text}')
        else:
            fetch_history_images.clear()
            st.session_state.history_page = 1

    except Exception as e:
        st.error(f'Erreur historique : {e}')

def fetch_images(query,page):
    try:return requests.get(f'{API_URL}/search-image',params={'query':query,'page':page},timeout=10).json()
    except:return []

def caption(data,instruction=''):
    payload=dict(data)
    if instruction.strip():payload['instruction_utilisateur']=instruction.strip()
    try:
        r=requests.post(f'{API_URL}/generate-caption',json=payload,timeout=30)
        return r.json().get('caption') if r.ok else None
    except:return None

def adapter_caption(data):
    try:
        r=requests.post(f'{API_URL}/adapt-caption',json=data,timeout=120)
        return r.json().get('adaptations') if r.ok else None
    except:return None

@st.cache_data(ttl=60, show_spinner=False)
def preview_flyer(entreprise, modele, langue, valeurs, image_bytes, fontes=None, couleur_filtre="#3F257C", opacite_filtre=0, _request_id=None):
    data = {
        'entreprise': entreprise,
        'modele': modele,
        'langue': langue,
        'valeurs': json.dumps(valeurs, ensure_ascii=False),
        'fontes': json.dumps(fontes or {}, ensure_ascii=False),
        'couleur_filtre': couleur_filtre,
        'opacite_filtre': opacite_filtre
    }

    files = (
        {'image_fond': ('image_fond.png', image_bytes, 'image/png')}
        if image_bytes
        else None
    )

    r = requests.post(
        f'{API_URL}/preview',
        data=data,
        files=files,
        headers={'X-Request-ID':_request_id} if _request_id else {},
        timeout=(5, 120)
    )
    r.raise_for_status()
    return r.content

config=api_get('/entreprises')
if not config: st.stop()
polices_google=api_get('/fonts') or {}
entreprises=list(config.keys())

onglet_creation, onglet_gestion = st.tabs([
    ":material/auto_awesome: Créer un flyer",
    ":material/business: Gestion"
])
with onglet_gestion:
    gestion_entreprises, gestion_modeles = st.tabs([
    ":material/business: Entreprises",
    ":material/palette: Modèles"
    ])
with gestion_entreprises:
    st.subheader("Entreprises")

    action = st.radio(
        "Action",
        ["Ajouter", "Modifier", "Supprimer"],
        horizontal=True,
        label_visibility="collapsed"
    )

    if action=='Ajouter':
        nom=st.text_input('Nom de l’entreprise'); officiel=st.text_input('Nom officiel'); secteur=st.text_input('Secteur d’activité'); mission=st.text_area('Mission')
        if st.button('➕ Ajouter l’entreprise', width='stretch'):
            r=requests.post(f'{API_URL}/entreprises',json={'nom':nom,'nom_officiel':officiel,'secteur_activite':secteur,'mission':mission})
            if r.ok: _api_get_json.clear(); st.success('Entreprise ajoutée.'); st.rerun()
            else: st.error(detail(r))
    elif action=='Modifier':
        e=st.selectbox('Entreprise',entreprises,key='edit_ent'); p=api_get(f'/entreprises/{e}') or {}
        officiel=st.text_input('Nom officiel',p.get('nom_officiel','')); secteur=st.text_input('Secteur',p.get('secteur_activite','')); mission=st.text_area('Mission',p.get('mission',''))
        if st.button('💾 Enregistrer', width='stretch'):
            r=requests.put(f'{API_URL}/entreprises/{e}',json={'nom_officiel':officiel,'secteur_activite':secteur,'mission':mission})
            if r.ok: _api_get_json.clear(); st.success('Modification enregistrée.'); st.rerun()
            else: st.error(detail(r))
    elif action=='Supprimer':
        e=st.selectbox('Entreprise',entreprises,key='del_ent')
        if st.button('🗑️ Supprimer', width='stretch'):
            r=requests.delete(f'{API_URL}/entreprises/{e}')
            if r.ok: _api_get_json.clear(); st.success('Entreprise supprimée.'); st.rerun()
            else: st.error(detail(r))
with gestion_modeles:
    st.subheader("Modèles")
    e=st.selectbox('Entreprise',entreprises,key='new_model_ent')

    catalogue_modeles=api_get(f'/modeles/{e}/catalogue') or {}
    modeles_existants=list(catalogue_modeles.get('modeles',{}).keys())

    action_modele=st.radio(
        'Action',
        ['Créer un modèle','Modifier un modèle','Supprimer un modèle'],
        horizontal=True,
        label_visibility='collapsed'
    )

    if action_modele=='Créer un modèle':

        nom=st.text_input(
            'Nom du nouveau modèle',
            placeholder='Ex: Recrutement_2026',
            key='new_model_name'
        )

        objectifs=catalogue_modeles.get('objectifs', [])
        choix=objectifs+['➕ Créer un nouvel objectif']

        obj=st.radio(
            'Objectif de la publication',
            choix,
            key='new_model_objective'
        )

        if obj=='➕ Créer un nouvel objectif':
            obj=st.text_input(
                'Nom du nouvel objectif',
                placeholder='Ex: Communication interne',
                key='custom_objective'
            )

        if nom.strip():
            result=afficher_editeur(e,nom.strip(),mode='nouveau')

            confirmation_modele=st.checkbox(
                'J’ai vérifié l’aperçu et les zones du modèle.',
                key=f'confirm_new_model_{e}_{nom.strip()}'
            ) if result else False

            if result and st.button(
                '💾 Enregistrer le modèle',
                type='primary',
                width='stretch',
                disabled=not confirmation_modele
            ):
                f=result.pop('_files')
                cfg=result['config']

                multipart={
                    'base_reference':('base.png',f['base'],'image/png'),
                    'calque_fixe':('overlay.png',f['overlay'],'image/png'),
                }

                r=requests.post(
                    f'{API_URL}/modeles/complet',
                    data={
                        'entreprise':e,
                        'modele':nom.strip(),
                        'objectif_publication':obj,
                        'zones_modifiables':json.dumps(cfg.get('zones_modifiables',{}),ensure_ascii=False)
                    },
                    files=multipart,
                    timeout=(10, 180)
                )

                if r.ok:
                    _api_get_json.clear()
                    st.session_state['modeles_details']={}
                    st.success('✅ Modèle enregistré avec succès.')
                    st.rerun()
                else:
                    st.error(detail(r))

    elif action_modele=='Modifier un modèle':
        modele_edit=st.selectbox('Modèle à modifier', modeles_existants, key='edit_modele')
        if st.session_state.get('modele_a_modifier') != modele_edit or st.session_state.get('entreprise_a_modifier') != e:
            r=requests.get(f'{API_URL}/modeles/{e}/{modele_edit}', timeout=10)
            if not r.ok:
                st.error(detail(r))
                st.stop()
            st.session_state['modele_a_modifier']=modele_edit
            st.session_state['entreprise_a_modifier']=e
            st.session_state['modele_config']=r.json()

        objectif_edit=st.text_input(
            'Objectif de publication',
            value=st.session_state['modele_config'].get('objectif_publication', ''),
            key=f'objectif_edit_{e}_{modele_edit}'
        )
        result=afficher_editeur(e, modele_edit, mode='modifier', config=st.session_state.get('modele_config'))
        if result and st.button('💾 Enregistrer les modifications', type='primary', width='stretch'):
            data={'zones_modifiables': json.dumps(result['config']['zones_modifiables']), 'objectif_publication': objectif_edit}
            try:
                with st.spinner('Enregistrement du modèle dans Supabase...'):
                    r=requests.put(
                        f'{API_URL}/modeles/{e}/{modele_edit}/fichiers',
                        data=data,
                        files=result['_changed_files'],
                        timeout=(10, 180)
                    )
                if r.ok:
                    st.session_state['modele_config']=r.json()['config']
                    _api_get_json.clear()
                    preview_flyer.clear()
                    st.session_state['modeles_details']={}
                    st.success('✅ Modèle modifié avec succès.')
                    st.rerun()
                else:
                    st.error(detail(r))
            except requests.RequestException as exc:
                st.error(f"La requête a expiré ou la connexion au backend a échoué : {exc}")
                st.warning("Vérifie ensuite le modèle dans l'application avant de relancer l'enregistrement : le serveur peut avoir terminé après l'expiration côté interface.")

    elif modeles_existants:
        modele_a_supprimer=st.selectbox(
            'Modèle à supprimer',
            modeles_existants,
            key='delete_model_selection'
        )
        st.warning(
            f"Cette action supprimera « {modele_a_supprimer} » de l’entreprise « {e} » "
            "ainsi que ses fichiers associés. Elle est définitive."
        )
        confirmer_suppression=st.checkbox(
            f"Je confirme la suppression de {modele_a_supprimer}",
            key=f'confirm_delete_model_{e}_{modele_a_supprimer}'
        )
        if st.button(
            '🗑️ Supprimer définitivement le modèle',
            type='primary',
            disabled=not confirmer_suppression,
            width='stretch'
        ):
            try:
                r=requests.delete(
                    f'{API_URL}/modeles/{e}/{modele_a_supprimer}',
                    timeout=60
                )
                if r.ok:
                    if st.session_state.get('modele_a_modifier') == modele_a_supprimer and st.session_state.get('entreprise_a_modifier') == e:
                        for cle in ('modele_a_modifier','entreprise_a_modifier','modele_config'):
                            st.session_state.pop(cle, None)
                    st.success(f"Le modèle « {modele_a_supprimer} » a été supprimé de « {e} ».")
                    _api_get_json.clear()
                    st.session_state['modeles_details']={}
                    st.rerun()
                else:
                    st.error(detail(r))
            except requests.RequestException as exc:
                st.error(f"La suppression a échoué ou le backend ne répond pas : {exc}")
    else:
        st.info("Cette entreprise ne contient aucun modèle à supprimer.")

with onglet_creation:
    col1,col2=st.columns([1.2,1])

    # Valeurs par défaut pour éviter les variables non définies
    modele=None
    model_cfg=None
    couleur_filtre="#3F257C"
    opacite_filtre=0
    mode='Uploader un fichier'
    generate_btn=False

    with col1:
        contexte_tab, contenu_tab, image_tab = st.tabs([
            "1. Contexte",
            "2. Contenu",
            "3. Image"
        ])

        with contexte_tab:
            entreprise=st.selectbox('Entreprise',entreprises,key='flyer_ent')

            # Récupérer le catalogue complet en une seule requête par entreprise.
            if entreprise not in st.session_state.modeles_details:
                catalogue=api_get(f'/modeles/{entreprise}/catalogue') or {}
                st.session_state.modeles_details[entreprise]=catalogue.get('modeles', {})

            modeles_details=st.session_state.modeles_details[entreprise]
            modeles=list(modeles_details)

            # Récupérer les objectifs depuis les données déjà chargées
            objectifs=[]
            for m in modeles:
                objectif_m=modeles_details.get(m,{}).get('objectif_publication')
                if objectif_m and objectif_m not in objectifs:
                    objectifs.append(objectif_m)

            if objectifs:
                objectif=st.radio('Objectif de la publication',objectifs,key='flyer_obj')
                modeles=[m for m in modeles if modeles_details.get(m,{}).get('objectif_publication')==objectif]

            modele=st.selectbox('Modèle',modeles,key='flyer_model') if modeles else None

            if modele:
                couleur_filtre=st.color_picker(
                    'Couleur du filtre',
                    value='#3F257C',
                    key=f'couleur_filtre_{entreprise}_{modele}'
                )
                opacite_filtre=st.slider(
                    'Opacite du filtre',
                    min_value=0,
                    max_value=100,
                    value=0,
                    format='%d%%',
                    key=f'opacite_filtre_{entreprise}_{modele}'
                )

            langue=st.selectbox('🌍 Langue du flyer',['Français','English','Español'])

            contexte_image=(entreprise,modele)
            contexte_precedent=st.session_state.image_model_context
            if contexte_precedent is not None and contexte_precedent!=contexte_image:
                st.session_state.image_valide_bytes=None
                st.session_state.image_croppee_bytes=None
                st.session_state.history_selection=None
                st.session_state.history_page=1
                st.session_state.bg_mode='Uploader un fichier'
                st.session_state.pop('bg_upload',None)
            st.session_state.image_model_context=contexte_image

        if modele:
            model_cfg=modeles_details.get(modele)
            if not model_cfg:
                model_cfg=api_get(f'/modeles/{entreprise}/{modele}')
                if model_cfg:
                    modeles_details[modele]=model_cfg
        else:
            model_cfg=None

        if model_cfg:

            with contenu_tab:
                valeurs={}

                zones_texte=sorted(
                    [(nom,zone) for nom,zone in model_cfg.get('zones_modifiables',{}).items() if zone.get('type')=='texte'],
                    key=lambda x:x[1].get('y',0)
                )

                fontes={}
                for nom,zone in zones_texte:
                    valeurs[nom]=st.text_input(nom.capitalize(),key=f'value_{nom}')

                    famille=st.selectbox(
                        f"Police — {nom}",
                        ["Par défaut"]+list(polices_google.keys()),
                        key=f"font_{nom}"
                    )

                    if famille!="Par défaut":
                        infos_police=polices_google[famille]
                        poids_disponibles=infos_police["weights"]

                        noms_poids={100:"Thin",200:"ExtraLight",300:"Light",400:"Regular",500:"Medium",600:"SemiBold",700:"Bold",800:"ExtraBold",900:"Black"}

                        options_poids=[(p,noms_poids.get(p,str(p))) for p in poids_disponibles]

                        weight_nom=st.selectbox(
                            f"Épaisseur — {nom}",
                            options_poids,
                            format_func=lambda x:x[1],
                            key=f"weight_{nom}"
                        )

                        weight=weight_nom[0]

                        styles_disponibles=polices_google[famille]["styles"]

                        style=st.selectbox(
                            f"Style — {nom}",
                            styles_disponibles,
                            format_func=lambda x:"Italic" if x=="italic" else "Normal",
                            key=f"style_{nom}"
                        )
                        
                        fontes[nom]={
                            "font":famille,
                            "weight":weight,
                            "style":style,
                            "size":int(zone.get("size",50))
                        }

                    couleur=st.color_picker(
                        f"Couleur du texte — {nom}",
                        value=st.session_state.get(f"text_color_{nom}", "#FFFFFF"),
                        key=f"text_color_{nom}"
                    )
                    fontes.setdefault(nom,{
                        "font":zone.get("font", "Inter"),
                        "weight":int(zone.get("weight", 400)),
                        "style":zone.get("style", "normal"),
                        "size":int(zone.get("size", 50))
                    })["color"]=couleur

                st.session_state['generation_values']=valeurs
                st.session_state['generation_fonts']=fontes

                st.session_state['texte_accompagnement_source']=st.text_area(
                    'Texte d’accompagnement à adapter',
                    value=st.session_state.get('texte_accompagnement_source',''),
                    height=160,
                    placeholder='Collez ici le texte que vous souhaitez adapter pour chaque réseau social.',
                    help='L’IA reformulera uniquement ce texte selon les règles de chaque plateforme.'
                )
                st.session_state['reseaux_accompagnement']=st.multiselect(
                    'Réseaux sociaux à préparer',
                    ['Facebook','TikTok','LinkedIn','Instagram','YouTube','Google Business Profile'],
                    default=['Facebook','Instagram','LinkedIn'],
                    key='caption_networks'
                )
                if st.button('✨ Adapter le texte pour les réseaux', width='stretch'):
                    texte_source=st.session_state.get('texte_accompagnement_source','').strip()
                    reseaux=st.session_state.get('reseaux_accompagnement',[])
                    if not texte_source:
                        st.warning('Collez d’abord un texte d’accompagnement à adapter.')
                    elif not reseaux:
                        st.warning('Sélectionnez au moins un réseau social.')
                    else:
                        with st.spinner('Adaptation du texte en cours...'):
                            adaptations=adapter_caption({
                                'entreprise':entreprise,
                                'template_type':modele,
                                'langue':langue,
                                'texte_source':texte_source,
                                'reseaux':reseaux,
                            })
                        if adaptations:
                            st.session_state.caption_adaptations=adaptations

                                

            with image_tab:
                sources_image=['Uploader un fichier','G'+chr(233)+'n'+chr(233)+'rer avec IA','Historique']
                if st.session_state.get('bg_mode') not in sources_image:
                    st.session_state.bg_mode=sources_image[0]
                mode=st.radio('Source :',sources_image,horizontal=True,label_visibility='collapsed',key='bg_mode')

                if mode=='Uploader un fichier':
                    up=st.file_uploader('Glissez votre image ici',type=['png','jpg','jpeg'],key='bg_upload')
                    if up:
                        st.session_state.image_valide_bytes=up.getvalue()

                elif mode=='Générer avec IA':
                    prompt=st.text_area('🎨 Décrivez l’image à générer',height=80)
                    if st.button('✨ Générer l’image', width='stretch'):
                        r=requests.post(f'{API_URL}/generate-image-ia',json={'prompt':prompt},timeout=120)
                        if r.ok:
                            st.session_state.image_valide_bytes=r.content
                            st.rerun()
                        else:
                            st.error(detail(r))

                elif mode=='Historique':
                    if 'history_page' not in st.session_state:
                        st.session_state.history_page = 1

                    try:
                        page_historique=fetch_history_images(st.session_state.history_page)
                    except requests.RequestException as e:
                        page_historique={'items': [], 'has_next': False}
                        st.error(f"Impossible de charger l'historique : {e}")

                    images_historique=page_historique.get('items', [])
                    if images_historique:
                        st.caption('Choisis une image de l’historique')
                        with ThreadPoolExecutor(max_workers=6) as executor:
                            futures=[
                                executor.submit(fetch_history_thumbnail, image['thumbnail_url'])
                                for image in images_historique
                            ]
                            miniatures=[]
                            for future in futures:
                                try:
                                    miniatures.append(future.result())
                                except Exception as exc:
                                    miniatures.append(exc)

                        colonnes=st.columns(4)
                        for index, image_historique in enumerate(images_historique):
                            nom_image=image_historique.get('nom',f'image_{index}')
                            url_image=image_historique['url']
                            with colonnes[index % len(colonnes)]:
                                try:
                                    if isinstance(miniatures[index], Exception):
                                        raise miniatures[index]
                                    st.image(miniatures[index],width=160)
                                    selectionnee=st.session_state.get('history_selection')==nom_image
                                    if st.button(
                                        '✓ Sélectionnée' if selectionnee else 'Choisir',
                                        key=f'history_select_{nom_image}',
                                        disabled=selectionnee,
                                        width='stretch'
                                    ):
                                        st.session_state.image_valide_bytes=fetch_history_image(url_image)
                                        st.session_state.image_croppee_bytes=None
                                        st.session_state.history_selection=nom_image
                                        st.rerun()
                                except Exception as exc:
                                    st.error(f"Miniature indisponible ({nom_image}) : {exc}")
                        precedente, indicateur_page, suivante = st.columns([1, 2, 1])
                        with precedente:
                            if st.button(
                                '← Précédent',
                                disabled=st.session_state.history_page <= 1,
                                key='history_previous_page',
                                width='stretch'
                            ):
                                st.session_state.history_page -= 1
                                st.rerun()
                        with indicateur_page:
                            st.caption(f"Page {st.session_state.history_page}")
                        with suivante:
                            if st.button(
                                'Suivant →',
                                disabled=not page_historique.get('has_next', False),
                                key='history_next_page',
                                width='stretch'
                            ):
                                st.session_state.history_page += 1
                                st.rerun()
                    else:
                        st.info("Aucune image dans l'historique. Veuillez générer ou télécharger une image d'abord.")

                if st.session_state.image_valide_bytes:
                    img=Image.open(io.BytesIO(st.session_state.image_valide_bytes)).convert('RGB')
                    zone_image=next((z for z in (model_cfg or {}).get('zones_modifiables',{}).values() if z.get('type')=='image'),None)

                    if zone_image and zone_image.get('largeur') and zone_image.get('hauteur'):
                        ratio_img=img.width/img.height
                        ratio_zone=float(zone_image['largeur'])/float(zone_image['hauteur'])

                        if abs(ratio_img-ratio_zone)>0.05:
                            preview=img.copy()
                            preview.thumbnail((700,700))

                            crop_scale=0.50

                            if preview.width/preview.height>ratio_zone:
                                crop_height=int(preview.height*crop_scale)
                                crop_width=int(crop_height*ratio_zone)
                            else:
                                crop_width=int(preview.width*crop_scale)
                                crop_height=int(crop_width/ratio_zone)

                            left=(preview.width-crop_width)//2
                            top=(preview.height-crop_height)//2

                            box=st_cropper(
                                preview,
                                aspect_ratio=(int(zone_image["largeur"]),int(zone_image["hauteur"])),
                                default_coords=(left,left+crop_width,top,top+crop_height),
                                box_color="blue",
                                return_type="box",
                                key=f"crop_{entreprise}_{modele}"
                            )

                            if box:
                                sx=img.width/preview.width
                                sy=img.height/preview.height

                                crop=img.crop((
                                    int(box["left"]*sx),
                                    int(box["top"]*sy),
                                    int((box["left"]+box["width"])*sx),
                                    int((box["top"]+box["height"])*sy)
                                ))

                                out=io.BytesIO()
                                crop.save(out,format="PNG")

                                st.session_state.image_croppee_bytes=out.getvalue()
                                st.image(crop)

                        else:
                            st.session_state.image_croppee_bytes=st.session_state.image_valide_bytes
                            st.image(img)

                    else:
                        st.session_state.image_croppee_bytes=st.session_state.image_valide_bytes
                        st.image(img,width=220)

                    if st.button('🗑️ Retirer l’image', width='stretch'):
                        st.session_state.image_valide_bytes=None
                        st.session_state.image_croppee_bytes=None
                        st.rerun()

        generate_btn=st.button('🎨 GÉNÉRER LE FLYER', type='primary', width='stretch')

    with col2:
        st.subheader('Aperçu')
        preview_zone=st.empty()

        if modele and model_cfg:
            valeurs_preview=st.session_state.get('generation_values',{})
            fontes_preview=st.session_state.get('generation_fonts',{})
            image_preview=st.session_state.image_croppee_bytes

            signature_preview=hashlib.sha256(json.dumps({
                'entreprise':entreprise,
                'modele':modele,
                'langue':langue,
                'valeurs':valeurs_preview,
                'fontes':fontes_preview,
                'couleur_filtre':couleur_filtre,
                'opacite_filtre':opacite_filtre,
                'image':hashlib.sha256(image_preview).hexdigest() if image_preview else None
            },ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()

            if (
                st.session_state.flyer_genere
                and st.session_state.flyer_genere_signature!=signature_preview
            ):
                st.session_state.flyer_genere=None
                st.session_state.flyer_genere_signature=None

            if image_preview and st.session_state.preview_flyer_signature!=signature_preview:
                request_id=uuid.uuid4().hex
                try:
                    with st.spinner('Actualisation de la prévisualisation...'):
                        st.session_state.preview_flyer_bytes=preview_flyer(
                            entreprise,
                            modele,
                            langue,
                            valeurs_preview,
                            image_preview,
                            fontes_preview,
                            couleur_filtre=couleur_filtre,
                            opacite_filtre=opacite_filtre,
                            _request_id=request_id
                        )
                    st.session_state.preview_flyer_signature=signature_preview
                    st.session_state.preview_flyer_error_signature=None
                    st.session_state.preview_flyer_error=None
                except requests.Timeout:
                    st.session_state.preview_flyer_bytes=None
                    st.session_state.preview_flyer_error_signature=signature_preview
                    st.session_state.preview_flyer_error=(
                        f"La prévisualisation a dépassé le délai d’attente. Référence : {request_id}"
                    )
                except requests.RequestException as exc:
                    response=getattr(exc,'response',None)
                    st.session_state.preview_flyer_bytes=None
                    st.session_state.preview_flyer_error_signature=signature_preview
                    st.session_state.preview_flyer_error=(
                        f"Prévisualisation refusée ou indisponible : "
                        f"{_api_error_message(response)}. Référence : {request_id}"
                    )

            if (
                st.session_state.preview_flyer_bytes
                and st.session_state.preview_flyer_signature==signature_preview
            ):
                preview=st.session_state.preview_flyer_bytes
                img_preview=Image.open(io.BytesIO(preview)).convert("RGB")
                img_preview=img_preview.filter(ImageFilter.GaussianBlur(radius=3))

                preview_zone.image(
                    img_preview,
                    caption='Prévisualisation — génération non terminée',
                    width='stretch'
                )
            elif not image_preview:
                st.info("Choisis une image importee, generee par IA ou depuis l'historique pour afficher l'apercu.")
            elif st.session_state.preview_flyer_error_signature==signature_preview:
                st.warning(st.session_state.preview_flyer_error or 'Prévisualisation indisponible.')
                if st.button('Réessayer la prévisualisation',key='retry_flyer_preview'):
                    st.session_state.preview_flyer_error_signature=None
                    st.rerun()
        else:
            st.session_state.preview_flyer_bytes=None
            st.session_state.preview_flyer_signature=None
            st.session_state.preview_flyer_error_signature=None
            st.session_state.preview_flyer_error=None

        flyer_zone=st.empty()

        # génération finale
        if generate_btn and modele and model_cfg and not st.session_state.image_croppee_bytes:
            st.warning("Choisis une image importee, generee par IA ou depuis l'historique avant de generer.")

        if generate_btn and modele and model_cfg and st.session_state.image_croppee_bytes:
            valeurs=st.session_state.get('generation_values',{})
            fontes=st.session_state.get('generation_fonts',{})
            image_bytes=st.session_state.image_croppee_bytes
            data={'entreprise':entreprise,'modele':modele,'langue':langue,'valeurs':json.dumps(valeurs,ensure_ascii=False), 'fontes':json.dumps(fontes,ensure_ascii=False),'couleur_filtre':couleur_filtre,'opacite_filtre':opacite_filtre}
            files={'image_fond':('image_fond.png',image_bytes,'image/png')} if image_bytes else None

            try:
                r=requests.post(f'{API_URL}/generate',data=data,files=files,timeout=120)

                if r.ok:
                    if image_bytes:
                        enregistrer_image_historique(image_bytes)

                    st.session_state.flyer_genere=r.content
                    st.session_state.flyer_genere_signature=signature_preview
                    preview_zone.empty()

                    st.session_state.derniere_data_flyer={'entreprise':entreprise,'template_type':modele,'langue':langue,**valeurs}

                else:
                    st.error(f'Erreur serveur : {r.text}')

            except Exception as e:
                st.error(f'Erreur de connexion : {e}')

        if st.session_state.flyer_genere:
            with flyer_zone.container():
                st.image(st.session_state.flyer_genere, caption='Votre flyer est prêt !', width='stretch')
                st.download_button('💾 TÉLÉCHARGER (PNG HD)', st.session_state.flyer_genere, f'Flyer_{entreprise}_{modele}.png'.replace(' ', '_'), 'image/png', width='stretch')

if st.session_state.caption_adaptations:
    st.divider(); st.subheader('Textes adaptés par réseau social')
    for reseau, resultat in st.session_state.caption_adaptations.items():
        st.markdown(f'**{reseau}** — {resultat["caracteres"]}/{resultat["maximum"]} caractères')
        st.text_area(f'Texte {reseau}', value=resultat['texte'], height=170, key=f'adaptation_{reseau}')
