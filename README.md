# Frontend — Générateur de Flyers

Application Streamlit contenant uniquement l'interface utilisateur.

## Lancer

Depuis ce dossier :

    streamlit run app.py

Le frontend communique avec le backend à :

    http://127.0.0.1:8000

Pour le déploiement, configurez `API_URL` dans les Secrets de Streamlit avec
l'URL publique du backend. En développement local, la valeur par défaut
`http://127.0.0.1:8000` reste utilisée.

## Règle

Le frontend ne contient pas la logique de génération des flyers.
Il envoie les demandes au backend et affiche les résultats.
