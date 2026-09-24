import io,json,os,requests,hashlib
from dotenv import load_dotenv
import streamlit as st
from PIL import Image, ImageOps, ImageFilter
from streamlit_image_select import image_select
from streamlit_cropper import st_cropper
from editeur_visuel import afficher_editeur

load_dotenv()
API_URL=os.getenv('API_URL','http://127.0.0.1:8000')
st.set_page_config(page_title='Générateur Flyers Pro',layout='wide',page_icon='✨')
st.title('✨ Visual Copilot AI')
st.caption('Générateur de flyers automatisé')


for key,default in {'image_valide_bytes':None,'img_page':1,'flyer_genere':None,'chat_caption':[],'caption_valide':False,'attente_consigne':False,'derniere_data_flyer':None,'image_croppee_bytes':None,'modeles_details': {}}.items():
    if key not in st.session_state: st.session_state[key]=default

def api_get(path,**kwargs):
    try:
        r=requests.get(f'{API_URL}{path}',timeout=20,**kwargs); r.raise_for_status(); return r.json()
    except Exception as e: st.error(f'Backend indisponible : {e}'); return None

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
def preview_flyer(entreprise, modele, langue, valeurs, image_bytes, fontes=None):
    data = {
        'entreprise': entreprise,
        'modele': modele,
        'langue': langue,
        'valeurs': json.dumps(valeurs, ensure_ascii=False),
        'fontes': json.dumps(fontes or {}, ensure_ascii=False)
    }

    files = (
        {'image_fond': ('image_fond.png', image_bytes, 'image/png')}
        if image_bytes
        else None
    )

    try:
        r = requests.post(
            f'{API_URL}/preview',
            data=data,
            files=files,
            timeout=30
        )

        return r.content if r.ok else None

    except Exception:
        return None

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
        if st.button('➕ Ajouter l’entreprise',use_container_width=True):
            r=requests.post(f'{API_URL}/entreprises',json={'nom':nom,'nom_officiel':officiel,'secteur_activite':secteur,'mission':mission})
            if r.ok: st.success('Entreprise ajoutée.'); st.rerun()
            else: st.error(detail(r))
    elif action=='Modifier':
        e=st.selectbox('Entreprise',entreprises,key='edit_ent'); p=api_get(f'/entreprises/{e}') or {}
        officiel=st.text_input('Nom officiel',p.get('nom_officiel','')); secteur=st.text_input('Secteur',p.get('secteur_activite','')); mission=st.text_area('Mission',p.get('mission',''))
        if st.button('💾 Enregistrer',use_container_width=True):
            r=requests.put(f'{API_URL}/entreprises/{e}',json={'nom_officiel':officiel,'secteur_activite':secteur,'mission':mission})
            if r.ok: st.success('Modification enregistrée.'); st.rerun()
            else: st.error(detail(r))
    elif action=='Supprimer':
        e=st.selectbox('Entreprise',entreprises,key='del_ent')
        if st.button('🗑️ Supprimer',use_container_width=True):
            r=requests.delete(f'{API_URL}/entreprises/{e}')
            if r.ok: st.success('Entreprise supprimée.'); st.rerun()
            else: st.error(detail(r))
with gestion_modeles:
    st.subheader("Modèles")
    e=st.selectbox('Entreprise',entreprises,key='new_model_ent')

    modeles_existants=api_get(f'/modeles/{e}') or []

    action_modele=st.radio(
        'Action',
        ['Créer un modèle','Modifier un modèle'],
        horizontal=True,
        label_visibility='collapsed'
    )

    if action_modele=='Créer un modèle':

        nom=st.text_input(
            'Nom du nouveau modèle',
            placeholder='Ex: Recrutement_2026',
            key='new_model_name'
        )

        objectifs=api_get(f'/objectifs/{e}') or []
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

            if result and st.button(
                '💾 Enregistrer le modèle',
                type='primary',
                use_container_width=True
            ):
                f=result.pop('_files')
                cfg=result['config']

                multipart={
                    'base_reference':('base.png',f['base'],'image/png'),
                    'calque_fixe':('overlay.png',f['overlay'],'image/png'),
                    'fond_defaut':('fond.png',f['fond'],'image/png')
                }

                r=requests.post(
                    f'{API_URL}/modeles/complet',
                    data={
                        'entreprise':e,
                        'modele':nom.strip(),
                        'objectif_publication':obj
                    },
                    files=multipart,
                    timeout=30
                )

                if r.ok:
                    save=requests.put(
                        f'{API_URL}/modeles/{e}/{nom.strip()}',
                        json={
                            'zones_modifiables':cfg.get('zones_modifiables',{}),
                            'objectif_publication':obj
                        },
                        timeout=10
                    )

                    if save.ok:
                        st.success('✅ Modèle enregistré avec succès.')
                        st.rerun()
                    else:
                        st.error(detail(save))
                else:
                    st.error(detail(r))

    else:

        modele_edit=st.selectbox(
        'Modèle à modifier',
        modeles_existants,
        key='edit_modele'
    )

    if st.button('✏️ Modifier',use_container_width=True):
        r=requests.get(
            f'{API_URL}/modeles/{e}/{modele_edit}',
            timeout=10
        )

        if r.ok:
            st.session_state['modele_a_modifier']=modele_edit
            st.session_state['modele_config']=r.json()
            st.rerun()
        else:
            st.error(detail(r))

    if st.session_state.get('modele_a_modifier'):
        modele_edit=st.session_state['modele_a_modifier']

        result=afficher_editeur (
            e,
            modele_edit,
            mode='modifier',
            config=st.session_state.get('modele_config')
        )

with onglet_creation:
    col1,col2=st.columns([1.2,1])

    # Valeurs par défaut pour éviter les variables non définies
    modele=None
    model_cfg=None
    mode='Par défaut'
    generate_btn=False

    with col1:
        contexte_tab, contenu_tab, image_tab = st.tabs([
            "1. Contexte",
            "2. Contenu",
            "3. Image"
        ])

        with contexte_tab:
            entreprise=st.selectbox('Entreprise',entreprises,key='flyer_ent')
            modeles=config.get(entreprise,[])

            # Charger les détails des modèles une seule fois
            if entreprise not in st.session_state.modeles_details:
                details={}
                for m in modeles:
                    c=api_get(f'/modeles/{entreprise}/{m}') or {}
                    details[m]=c
                st.session_state.modeles_details[entreprise]=details

            modeles_details=st.session_state.modeles_details[entreprise]

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
            langue=st.selectbox('🌍 Langue du flyer',['Français','English','Español'])

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

                st.session_state['generation_values']=valeurs
                st.session_state['generation_fonts']=fontes

                                

            with image_tab:
                mode=st.radio('Source :',['Par défaut','Uploader un fichier','Générer avec IA','Historique'],horizontal=True,label_visibility='collapsed',key='bg_mode')

                if mode=='Uploader un fichier':
                    up=st.file_uploader('Glissez votre image ici',type=['png','jpg','jpeg'],key='bg_upload')
                    if up:
                        st.session_state.image_valide_bytes=up.getvalue()

                elif mode=='Générer avec IA':
                    prompt=st.text_area('🎨 Décrivez l’image à générer',height=80)
                    if st.button('✨ Générer l’image',use_container_width=True):
                        r=requests.post(f'{API_URL}/generate-image-ia',json={'prompt':prompt},timeout=120)
                        if r.ok:
                            st.session_state.image_valide_bytes=r.content
                            st.rerun()
                        else:
                            st.error(detail(r))

                elif mode=='Historique':
                    images_historique=api_get('/historique') or []

                    if images_historique:
                        urls=[image['url'] for image in images_historique]

                        choix=image_select(
                            'Cliquez sur l’image :',
                            urls,
                            use_container_width=True
                        )

                        if choix:
                            try:
                                r=requests.get(choix,timeout=20)

                                if r.ok:
                                    st.session_state.image_valide_bytes=r.content
                                else:
                                    st.error('Impossible de charger cette image.')

                            except Exception as e:
                                st.error(f'Erreur lors du chargement : {e}')
                    else:
                        st.info("Aucune image dans l'historique. Veuillez générer ou télécharger une image d'abord.")

                if mode=='Par défaut':
                    st.session_state.image_valide_bytes=None
                    st.session_state.image_croppee_bytes=None      
                if st.session_state.image_valide_bytes and mode!='Par défaut':
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

                    if st.button('🗑️ Retirer l’image',use_container_width=True):
                        st.session_state.image_valide_bytes=None
                        st.session_state.image_croppee_bytes=None
                        st.rerun()

        generate_btn=st.button('🎨 GÉNÉRER LE FLYER',type='primary',use_container_width=True)

    with col2:
        st.subheader('Aperçu')
        preview_zone=st.empty()

        if not st.session_state.flyer_genere and modele and model_cfg:
            valeurs_preview=st.session_state.get('generation_values',{})
            fontes_preview=st.session_state.get('generation_fonts',{})
            image_preview=st.session_state.image_croppee_bytes if mode!='Par défaut' else None

            preview=preview_flyer(
                entreprise,
                modele,
                langue,
                valeurs_preview,
                image_preview,
                fontes_preview
            )

            if preview:
                img_preview=Image.open(io.BytesIO(preview)).convert("RGB")
                img_preview=img_preview.filter(ImageFilter.GaussianBlur(radius=3))

                preview_zone.image(
                    img_preview,
                    caption='Prévisualisation — génération non terminée',
                    use_container_width=True
                )

        flyer_zone=st.empty()

        # génération finale
        if generate_btn and modele and model_cfg:
            valeurs=st.session_state.get('generation_values',{})
            fontes=st.session_state.get('generation_fonts',{})
            image_bytes=st.session_state.image_croppee_bytes if mode!='Par défaut' else None
            data={'entreprise':entreprise,'modele':modele,'langue':langue,'valeurs':json.dumps(valeurs,ensure_ascii=False), 'fontes':json.dumps(fontes,ensure_ascii=False)}
            files={'image_fond':('image_fond.png',image_bytes,'image/png')} if image_bytes else None

            try:
                r=requests.post(f'{API_URL}/generate',data=data,files=files,timeout=120)

                if r.ok:
                    if image_bytes:
                        enregistrer_image_historique(image_bytes)

                    st.session_state.flyer_genere=r.content
                    preview_zone.empty()

                    caption_data={'entreprise':entreprise,'template_type':modele,'langue':langue,**valeurs}
                    st.session_state.derniere_data_flyer=caption_data

                    txt=caption(caption_data)
                    st.session_state.chat_caption=[{'role':'assistant','content':txt}] if txt else []
                    st.session_state.caption_valide=False
                    st.session_state.attente_consigne=False

                else:
                    st.error(f'Erreur serveur : {r.text}')

            except Exception as e:
                st.error(f'Erreur de connexion : {e}')

        if st.session_state.flyer_genere:
            with flyer_zone.container():
                st.image(st.session_state.flyer_genere,caption='Votre flyer est prêt !',use_container_width=True)
                st.download_button('💾 TÉLÉCHARGER (PNG HD)',st.session_state.flyer_genere,f'Flyer_{entreprise}_{modele}.png'.replace(' ','_'),'image/png',use_container_width=True)

if st.session_state.chat_caption:
    st.divider(); st.subheader('Texte généré')
    for msg in st.session_state.chat_caption:
        with st.chat_message(msg['role']): st.write(msg['content'])
    if not st.session_state.caption_valide and not st.session_state.attente_consigne:
        st.write('**Ce texte vous convient-il ?**'); a,b=st.columns(2)
        if a.button('✅ Oui, je valide',use_container_width=True): st.session_state.caption_valide=True; st.rerun()
        if b.button('✏️ Non, je veux modifier',use_container_width=True): st.session_state.attente_consigne=True; st.rerun()
    elif st.session_state.attente_consigne:
        consigne=st.chat_input('Dites-moi comment vous voulez que je le réécrive...')
        if consigne:
            st.session_state.chat_caption.append({'role':'user','content':consigne}); txt=caption(st.session_state.derniere_data_flyer,consigne)
            if txt: st.session_state.chat_caption.append({'role':'assistant','content':txt})
            st.session_state.attente_consigne=False; st.rerun()
    else: st.success('✅ Texte validé — il est prêt à être copié/utilisé.')
