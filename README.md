# Ollaya Decision Models for Home Assistant OS — v0.1.7

**[Français](README.fr.md) | English**

Local, CPU-only Ollaya inference with model management, a Home Assistant ingress UI, and an authenticated API for n8n and other internal clients.

## Changes in 0.1.7

- Fix language catalog directory permissions preventing startup under the unprivileged `ollaya` user on Home Assistant OS.
- Add a Docker build-time English/French catalog smoke test executed as `ollaya`.
- Preserve the bilingual UI, model management settings, and upstream Ollaya `:latest` policy from v0.1.6.

## Features retained from 0.1.6

- **Model management / Gestion des modèles** replaces the old *Model downloads* user-visible option label. The stored option key `model_downloads_enabled` is **unchanged**, preserving existing Home Assistant configuration.
- When disabled, **both install and remove actions** are hidden **and enforced server-side**. Listing, selecting an installed model, resetting the default, diagnostics, and inference remain available.
- Native Home Assistant settings translations in `ollaya/translations/en.yaml` and `fr.yaml`.
- Ingress manager English and French catalogs with browser-language detection and an explicit language switch; choice is saved as a non-sensitive cookie.
- English docs in `ollaya/DOCS.md`, French docs in `ollaya/docs/fr.md`.
- Existing API compatibility, `/data/ollaya/models` storage, privacy-safe diagnostics, and Ollaya `:latest` CPU base image retained.

## Installation or upgrade

Copy **the contents of `ollaya/`** to `/addons/local/ollaya/`, refresh the Home Assistant app store, **rebuild/update** the app image to version `0.1.7`, and restart. A simple restart of the old container will not pick up the translations or Python changes. Existing model data and API keys are not intentionally changed.

For full installation steps, configuration, and private networking see [English documentation](ollaya/DOCS.md) or [documentation française](ollaya/docs/fr.md).

**Scope:** Experimental CPU edition for Generic x86-64 Home Assistant OS. The application is based on Ollaya [upstream](https://github.com/ollaya-dev/ollaya) and uses the upstream moving `ghcr.io/ollaya-dev/ollaya:latest` image by design. On rebuild it may change runtime version. GPU support is not yet packaged; see [GPU_SUPPORT.md](GPU_SUPPORT.md).

Testing: local automated tests use a simulated Ollaya engine; a real Home Assistant build and bilingual frontend check must still be performed after installation.
