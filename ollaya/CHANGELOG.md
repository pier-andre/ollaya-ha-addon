# Changelog / Journal des modifications

## Non publié

## 0.1.11

- Fix the weights exclusion. `backup_exclude` entries are matched with `Path.match` against `/data/addons/data/<slug>/<path>`, right-anchored, so the absolute `/data/ollaya/models` added in 0.1.10 never matched and every backup still carried ~4.1 GB of weights. The pattern is now `*/ollaya/models`; a directory that matches is not walked, so all of its content is left out. Confirmed on a throwaway app: the excluded tree was absent from the archive and the rest was present.
- Nothing else changes: no option, no default and no runtime path is touched.

### Résumé 0.1.11

- Correction de l'exclusion des poids. Les entrées de `backup_exclude` sont comparées par `Path.match` à `/data/addons/data/<slug>/<chemin>`, ancré à droite : le chemin absolu `/data/ollaya/models` ajouté en 0.1.10 ne correspondait jamais et chaque sauvegarde transportait encore environ 4,1 Go de poids. Le motif devient `*/ollaya/models` ; un dossier qui correspond n'est pas parcouru, tout son contenu est donc écarté de l'archive. Vérifié sur une application jetable : l'arborescence exclue était absente, le reste présent.
- Aucun autre changement : ni option, ni valeur par défaut, ni chemin d'exécution.

## 0.1.10

- New **`model_directory`** option with two locations: `/data/ollaya` (default, unchanged) and `/share/ollaya`. Weights live in `<model_directory>/models`; `/share` is now mapped read-write so the second choice is reachable at all.
- `/data/ollaya/models` is declared in `backup_exclude`. A Home Assistant backup of this app keeps its options, API key and selected model but no longer carries the 4–5 GB of weights, which were inflating every backup and are reproducible by pulling again.
- Switching the option does not move existing models: the startup script only creates the target directory. It resolves the option once, rejects anything outside the two documented paths, and exports `OLLAYA_HA_MODELS`; the server logs that path, shows it in ingress and passes it to the daemon as `OLLAYA_MODELS`.
- `/config` is deliberately not offered. Giving an inference app write access to the whole Home Assistant configuration is not required to fix backup size.
- Startup regression test now asserts the resolved path, plus a new case that aborts startup on an unknown `model_directory`.

### Résumé 0.1.10

- Nouvelle option **`model_directory`** à deux emplacements : `/data/ollaya` (par défaut, inchangé) et `/share/ollaya`. Les poids sont stockés dans `<model_directory>/models` ; `/share` est désormais monté en lecture-écriture pour rendre le second choix accessible.
- `/data/ollaya/models` est déclaré dans `backup_exclude` : une sauvegarde Home Assistant conserve les options, la clé API et le modèle sélectionné, mais ne transporte plus les 4 à 5 Go de poids, reproductibles par un nouveau téléchargement.
- Changer d’option ne déplace pas les modèles existants : le script de démarrage crée seulement le dossier cible. Il résout l’option une fois, refuse tout chemin hors des deux emplacements documentés et exporte `OLLAYA_HA_MODELS` ; le serveur journalise ce chemin, l’affiche dans l’interface et le transmet au moteur sous `OLLAYA_MODELS`.
- `/config` n’est volontairement pas proposé : donner à une application d’inférence l’accès en écriture à toute la configuration Home Assistant n’est pas nécessaire pour régler la taille des sauvegardes.
- Le test de démarrage vérifie désormais le chemin résolu, avec un nouveau cas qui interrompt le démarrage sur un `model_directory` inconnu.

## 0.1.9

- The CPU-only nature of the app is now explicit in the app description, in the startup log (`CPU-only edition: Ollaya runs with OLLAYA_DEVICE=cpu`) and in the English/French documentation. `OLLAYA_DEVICE` is fed by a single `DEVICE` constant instead of a literal.
- Removed `stage: experimental` from `config.yaml`; the app no longer declares an experimental stage.
- GPU/CUDA notes moved from `GPU_SUPPORT.md` to `docs/gpu/README.md` and expanded with the verified reasons CUDA cannot work on Home Assistant OS (no NVIDIA driver, no GPU runtime in the Supervisor) and the install types and conditions under which it could.
- No configuration, model or storage migration.

### Résumé 0.1.9

- Le caractère réservé au CPU est désormais explicite dans la description de l’application, dans le journal de démarrage (`OLLAYA_DEVICE=cpu`) et dans la documentation anglaise et française.
- Suppression de `stage: experimental` dans `config.yaml`.
- Les notes GPU/CUDA passent de `GPU_SUPPORT.md` à `docs/gpu/README.md`, avec les raisons vérifiées de l’impossibilité de CUDA sur Home Assistant OS et les conditions d’une évolution.
- Aucune migration de configuration, de modèles ou de stockage.

## 0.1.8

- Upstream base image pinned to `ghcr.io/ollaya-dev/ollaya:0.18.0` instead of `:latest`. Both tags pointed at the same image digest (`sha256:a1baf26a…`) when this release was cut, so nothing changes at runtime; rebuilds become reproducible and the Ollaya runtime can now be updated by a Renovate pull request.
- `renovate.json`: the rule that disabled the image is replaced by a `versioning` rule accepting only `X.Y.Z` tags, so the CUDA tags (`-cuda`, `-cuda12`) are never offered for this CPU edition.
- No configuration, model or storage migration.

### Résumé 0.1.8

- Image Ollaya épinglée à `0.18.0` au lieu de `:latest` (même empreinte, donc aucun changement de comportement) : reconstruction reproductible et mises à jour désormais proposées par Renovate.
- Les images CUDA restent exclues ; aucune migration de configuration ni de modèles.

## 0.1.7

- Fix service startup failure on Home Assistant after enabling localization: explicitly create `/usr/local/lib/i18n` with directory mode `0755`, and ensure both catalogs are root-owned files with mode `0644`.
- Verify English/French catalog readability and JSON validity as the unprivileged `ollaya` user **during the image build**.
- No configuration migration; persistent models, API key, port settings and Ollaya `:latest` base image remain unchanged.

### Resume 0.1.7

- Corrige l'erreur de permission au demarrage des traductions ; verification de lecture des deux catalogues par le compte non privilegie pendant la construction de l'image.
- Aucun changement aux modeles, aux options ou a l'image Ollaya `:latest`.

## 0.1.6

- UI settings rename: **Model management / Gestion des modèles**, retaining the internal key `model_downloads_enabled` for backwards compatibility.
- Both pull and delete are disallowed when management is off; users can still select installed models.
- Home Assistant option translations: English and French.
- Ingress UI translations: English and French, browser preference, manual override and persistent language cookie.
- English and French install, networking, and troubleshooting documentation.
- Regression tests for both management operations and localization.
- Upstream base image remains `ghcr.io/ollaya-dev/ollaya:latest`, CPU-only.

### Résumé 0.1.6

- Libellé d’option **Gestion des modèles**, avec conservation de la clé interne `model_downloads_enabled`.
- Installation et suppression interdites quand la gestion est désactivée ; sélection des modèles déjà installés toujours possible.
- Traductions des options Home Assistant et de l’interface Web en anglais et en français, avec choix manuel mémorisé.
- Documentation et tests bilingues ; image CPU Ollaya `:latest` conservée.

## 0.1.5

- Graceful HTTP client disconnect handling; privacy-safe inference telemetry, ingress diagnostics and authenticated `/health`.

## 0.1.4

- Direct loopback HTTP (no proxy environment interference); upstream model-pull error diagnostics and completion validation.

## 0.1.3

- Ingress chunked POST support and input-size validation.

## 0.1.2

- Explicit persistent model store under `/data/ollaya/models`.

## 0.1.1

- Secure configuration staging before dropping root privileges.
