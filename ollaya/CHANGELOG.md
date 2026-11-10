# Changelog / Journal des modifications

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
