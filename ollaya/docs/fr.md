# Ollaya Decision Models — documentation de l’application Home Assistant

**Français | [English](../DOCS.md)**

## Fonction et compatibilité

**Cette application est une édition réservée au CPU.** Elle exécute des modèles de décision Ollaya localement, sur le processeur, dans Home Assistant OS Generic x86-64 : elle utilise la variante CPU de `ghcr.io/ollaya-dev/ollaya:0.18.0`, le périphérique est fixé à `cpu` dans le code de l’application, le journal de démarrage l’indique, et aucune option ne permet d’activer l’accélération matérielle. Home Assistant OS ne fournit aucun pilote NVIDIA et le Supervisor ne peut pas demander d’accès GPU : l’accélération n’est donc pas une propriété que cette application peut promettre. Les raisons vérifiées, les types d’installation où elle pourrait théoriquement fonctionner et les étapes restantes sont décrites dans [`docs/gpu/README.md`](https://github.com/pier-andre/ollaya-ha-addon/blob/main/docs/gpu/README.md).

L’image upstream est épinglée plutôt que mobile : une reconstruction redonne toujours le même moteur, et une nouvelle version d’Ollaya arrive sous forme de pull request Renovate, qui met à jour cette ligne, le `version:` de l’application et le journal des modifications dans la même PR. Les images CUDA ne sont jamais proposées ici.

## Installation / mise à jour

1. Ajoutez `https://github.com/pier-andre/ollaya-ha-addon` comme dépôt d’applications (menu ⋮ → **Dépôts**) puis installez **Ollaya Decision Models** ; pour du développement local, copiez plutôt le contenu du dossier `ollaya/` dans `/addons/local/ollaya/`. Le dépôt doit rester public : le Supervisor le clone sans identifiants.
2. Actualisez le magasin d’applications, installez ou **reconstruisez/mettez à jour** l’application et vérifiez la version **0.1.9**.
3. Configurez puis démarrez l’application. Ouvrez **Open Web UI** pour accéder à l’interface Web intégrée (ingress).
4. Activez **Gestion des modèles**, enregistrez et redémarrez l’application.
5. Installez `laya:en` ou un autre modèle enregistré dans Ollaya. Vérifiez sa présence dans « Modèles installés ».
6. Désactivez ensuite **Gestion des modèles**, enregistrez et redémarrez. Les modèles installés restent sélectionnables et l’inférence continue de fonctionner localement.

**Mise à jour sans migration :** la clé de configuration `model_downloads_enabled` reste inchangée pour conserver vos réglages. Sa portée couvre maintenant **l’installation et la suppression**, toutes deux interdites quand l’option est désactivée. Il n’est pas nécessaire de déplacer ni supprimer `/data/ollaya/`.

## Configuration

| Libellé | Clé interne | Valeur initiale | Fonction |
|---|---|---|---|
| Modèle par défaut | `default_model` | `laya:en` | Utilisé quand la requête n'indique pas de modèle. Un choix dans l’interface prévaut jusqu’à sa réinitialisation. |
| Gestion des modèles | `model_downloads_enabled` | `false` | Autorise **l’installation et la suppression** ; à désactiver hors des périodes de maintenance. |
| Durée de conservation en mémoire | `keep_alive` | `5m` | Temps avant de décharger un modèle inactif. |
| Nombre maximal de modèles chargés | `max_loaded_models` | `1` | Recommandé avec peu de RAM. |
| Fils d’exécution CPU | `threads` | `2` | À ajuster selon la charge de la machine. |
| Taille maximale de la file d’attente | `max_queue` | `16` | Limite les requêtes en attente. |
| Clé API | `api_key` | vide | Laisser vide pour générer une clé persistante, visible dans l’interface. Une clé personnalisée doit compter au moins 16 caractères. |

Les libellés des options Home Assistant utilisent `translations/en.yaml` et `translations/fr.yaml`, selon la langue du compte Home Assistant. L’interface Web intégrée est traduite séparément : elle détecte la langue du navigateur via `Accept-Language`, et propose le choix **English / Français** en haut de la page. Un témoin de langue non sensible conserve ce choix. La langue du navigateur peut différer de celle de Home Assistant.

## Modèles et stockage

Les poids des modèles sont conservés dans `/data/ollaya/models`, un emplacement persistant et privé à cette application. La clé API générée et le choix du modèle se trouvent dans `/data/ollaya/`. Le fichier `/data/options.json` est géré séparément par Supervisor. La mise à jour ne nécessite aucun déplacement de données.

`laya:en` désigne le modèle anglophone. L’alias `laya` installe les modèles anglais et multilingue; `laya:multilingual` désigne le modèle multilingue seul. L’installation accepte les modèles **enregistrés dans le registre Ollaya**, et non des URL Hugging Face arbitraires. Le téléchargement contacte le registre et les serveurs Hugging Face ; **l’inférence est locale**. Désactiver la gestion des modèles protège les commandes de l’application, mais **ne constitue pas un pare-feu sortant**.

## Réseau local et n8n

- `127.0.0.1:11436` — moteur Ollaya accessible seulement dans le conteneur.
- `8099` — gestionnaire Web via ingress Home Assistant, authentifié ; le serveur d’administration accepte seulement la passerelle ingress.
- `11435` — proxy d’inférence authentifié accessible au réseau interne des applications Home Assistant. L’exposition d’un port hôte ou LAN est **désactivée par défaut** (`11435/tcp: null`).
- L’API cliente ne donne aucun accès à `/api/pull`, `/api/delete`, `/api/create` ou `/api/copy`.

Pour n8n installé comme application Home Assistant, essayez `http://local-ollaya:11435/api/decide` (vérifiez le nom DNS réel). Transmettez l’en-tête `Authorization: Bearer <clé API>` et un corps JSON (`Content-Type: application/json`). Le modèle sélectionné est ajouté automatiquement si le champ `model` est absent. Le point de contrôle authentifié `GET /health` renvoie 200 lorsque le moteur répond, sinon 503.

Si n8n s’exécute sur un autre ordinateur, vous pouvez publier le port 11435 sur votre réseau local. **Ne faites pas de redirection de port Internet** ; limitez l’accès avec un pare-feu ou un VPN privé. La publication d’un port Home Assistant ne garantit pas, à elle seule, son isolement d’Internet.

## Diagnostics et confidentialité

Le tableau de bord présente l’état et la version du moteur, les modèles chargés, les succès et erreurs d’inférence, les délais dépassés, les déconnexions, la durée moyenne et les 25 dernières requêtes résumées. Ces statistiques sont conservées en mémoire et réinitialisées au redémarrage ; elles n’enregistrent ni texte de courriel, ni corps de requête, ni en-tête d’authentification. Les messages d’erreur renvoyés par Ollaya pendant un téléchargement peuvent rester en anglais.

## Dépannage

- **Installation ou suppression impossible :** activez Gestion des modèles dans la configuration et redémarrez. Cette option protège **les deux** opérations.
- **Libellé non traduit dans Home Assistant :** actualisez le magasin d’applications après reconstruction et vérifiez la langue de l’interface Home Assistant. La clé interne reste inchangée volontairement.
- **Mauvaise langue dans le gestionnaire :** utilisez English / Français en haut de la page. La langue du navigateur peut différer de celle de Home Assistant.
- **Erreur 502 du registre :** vérifiez le DNS et l’accès HTTPS sortant au registre Ollaya et à Hugging Face pendant l’installation.
- **Modèle non chargé :** les fichiers sont téléchargés sur disque ; la première requête peut déclencher le chargement en RAM. Consultez les diagnostics.
- **Délai d’attente dépassé dans n8n :** augmentez prudemment le délai, limitez le parallélisme, et ne déplacez pas de courriel si la classification échoue.

## Limitations

Les tests automatisés locaux utilisent un moteur Ollaya simulé et ne remplacent pas un essai réel avec Home Assistant Supervisor. Cette application est réservée au CPU : elle n’utilise aucun GPU et ne peut pas en activer un. Les raisons vérifiées, les types d’installation où l’accélération pourrait fonctionner et les étapes restantes sont décrites dans [`docs/gpu/README.md`](https://github.com/pier-andre/ollaya-ha-addon/blob/main/docs/gpu/README.md).

## Nouveautés v0.1.9

Le caractère réservé au CPU est désormais explicite dans la description de l’application, dans le journal de démarrage (`OLLAYA_DEVICE=cpu`) et dans cette documentation. La mention `stage: experimental` est retirée de `config.yaml`, et les notes GPU/CUDA sont déplacées vers `docs/gpu/README.md` avec l’explication de ce qui est possible ou non selon le type d’installation. Aucune migration de configuration, de modèles ou de stockage.

## Nouveautés v0.1.8

L'image de base passe de `:latest` à `ghcr.io/ollaya-dev/ollaya:0.18.0`. Les deux étiquettes pointaient vers la même empreinte au moment de la publication : rien ne change à l'exécution, mais la reconstruction devient reproductible et Renovate peut désormais proposer les versions suivantes. Aucune migration de configuration ni de modèles.

## Correction v0.1.7

La version v0.1.7 corrige les droits d'accès au dossier de traductions (`/usr/local/lib/i18n`) et valide la lecture du français et de l'anglais pendant la construction de l'image. Reconstruisez l'application : un simple redémarrage de v0.1.6 ne suffit pas. Les modèles restent stockés dans `/data/ollaya/models`.
