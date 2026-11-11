# Ollaya Decision Models pour Home Assistant OS — v0.1.9

**Français | [English](README.md)**

Application Home Assistant à inférence Ollaya locale sur processeur (CPU), avec gestion des modèles dans l’interface Web intégrée et API authentifiée pour n8n et les autres applications du réseau interne.

## Nouveautés de la version 0.1.9

- Le caractère réservé au CPU est désormais explicite là où il importe : description de l’application, journal de démarrage (`CPU-only edition: Ollaya runs with OLLAYA_DEVICE=cpu`) et documentation anglaise et française. `OLLAYA_DEVICE` provient d’une constante `DEVICE` unique dans `server.py`.
- La mention `stage: experimental` est retirée de `ollaya/config.yaml` : l’application ne se déclare plus expérimentale.
- Les notes GPU/CUDA passent de `GPU_SUPPORT.md` à [`docs/gpu/README.md`](docs/gpu/README.md), avec les limites vérifiées de Home Assistant (aucun pilote NVIDIA dans Home Assistant OS, aucun accès GPU dans le Supervisor) et les conditions d’une future édition GPU.
- Aucune migration de configuration, de modèles ou de stockage.

## Nouveautés de la version 0.1.8

- Image Ollaya épinglée à `ghcr.io/ollaya-dev/ollaya:0.18.0` au lieu de `:latest`. Les deux étiquettes partageaient la même empreinte à la publication : rien ne change à l'exécution, mais la reconstruction devient reproductible et Renovate peut proposer les nouvelles versions d'Ollaya (les images CUDA restent exclues).

## Nouveautés de la version 0.1.7

- Corrige les permissions du dossier de traduction qui empêchaient le démarrage du service Ollaya après la mise à jour précédente.
- Vérifie pendant la construction que le compte `ollaya` peut lire les fichiers anglais et français.
- Conserve la gestion des modèles, les paramètres bilingues et l'image Ollaya `:latest`.

## Fonctionnalités conservées de la version 0.1.6

- Le libellé « Téléchargements de modèles » devient **« Gestion des modèles »**. La clé interne `model_downloads_enabled` **ne change pas**, afin de conserver la configuration existante.
- Lorsque cette option est désactivée, **l’installation et la suppression** sont interdites côté serveur et masquées dans l’interface. La consultation, la sélection des modèles déjà installés, la réinitialisation du modèle par défaut, les diagnostics et l’inférence restent accessibles.
- Traductions natives des options Home Assistant : `ollaya/translations/en.yaml` et `fr.yaml`.
- Interface de gestion en anglais et en français, avec détection de la langue du navigateur et sélecteur manuel. Le choix est mémorisé dans un témoin de langue sans données sensibles.
- Documentation en [anglais](ollaya/DOCS.md) et en [français](ollaya/docs/fr.md).
- Conservation de l’API actuelle, des modèles dans `/data/ollaya/models`, des diagnostics sans contenu de courriel et de l’image Ollaya CPU `:latest`.

## Installation ou mise à jour

**Depuis ce dépôt (recommandé) :** dans Home Assistant, ouvrez **Paramètres → Applications → Magasin d’applications** → menu ⋮ → **Dépôts**, ajoutez `https://github.com/pier-andre/ollaya-ha-addon` (le dépôt doit rester public : le Supervisor le clone sans identifiants), puis installez **Ollaya Decision Models** et démarrez-la. L’application vit dans le dossier `ollaya/`, dont le nom est son identifiant : elle devient `<empreinte>_ollaya`, avec ses données dans `/data/apps/data/<empreinte>_ollaya`. Passer d’une copie locale dans `/addons` implique donc de déplacer ce dossier.

**Depuis une copie locale (développement) :** copiez **le contenu du dossier `ollaya/`** dans `/addons/local/ollaya/`, actualisez le magasin des applications Home Assistant, puis **reconstruisez/mettez à jour l’image** vers la version `0.1.9` et redémarrez. Un simple redémarrage de l’ancien conteneur ne suffit pas. Les modèles installés et les clés API existantes ne doivent pas être modifiés.

Les mises à jour sont automatisées par l’[application Renovate](https://github.com/pier-andre/renovate-ha-addon), qui lit le fichier `renovate.json` à la racine de ce dépôt.

Consultez la [documentation en français](ollaya/docs/fr.md) pour les instructions complètes, la configuration et la sécurité du réseau local.

**Portée :** édition réservée au CPU pour Home Assistant OS Generic x86-64. L’application s’exécute toujours sur le processeur : le périphérique est fixé à `cpu` dans `server.py` et l’image est la version CPU épinglée `ghcr.io/ollaya-dev/ollaya:0.18.0`, maintenue par l’application Renovate : une reconstruction ne change plus le moteur en silence. L’accélération GPU n’est pas empaquetée et ne peut pas être activée ici ; les raisons vérifiées et les conditions d’une future édition GPU sont dans [docs/gpu/README.md](docs/gpu/README.md).

Les tests automatisés utilisent un moteur Ollaya simulé. Il reste nécessaire de vérifier la construction réelle sur Home Assistant OS et l’affichage de l’interface bilingue après installation.
