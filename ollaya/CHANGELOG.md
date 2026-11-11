# Changelog / Journal des modifications

## Non publié

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
