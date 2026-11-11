# Ollaya Decision Models for Home Assistant OS — v0.1.9

**[Français](README.fr.md) | English**

Local, CPU-only Ollaya inference with model management, a Home Assistant ingress UI, and an authenticated API for n8n and other internal clients.

## Changes in 0.1.9

- The CPU-only nature of the app is now stated where it matters: the app description, the startup log (`CPU-only edition: Ollaya runs with OLLAYA_DEVICE=cpu`) and the English/French documentation. `OLLAYA_DEVICE` is fed by a single `DEVICE` constant in `server.py` instead of a literal.
- The `experimental` stage declaration was removed from `ollaya/config.yaml`; the app no longer labels itself experimental.
- GPU/CUDA notes moved from `GPU_SUPPORT.md` to [`docs/gpu/README.md`](docs/gpu/README.md), with the verified Home Assistant limitations (no NVIDIA driver in Home Assistant OS, no GPU runtime in the Supervisor) and the conditions under which a GPU edition could exist.
- No configuration, model or storage migration.

## Changes in 0.1.8

- Upstream base image pinned to `ghcr.io/ollaya-dev/ollaya:0.18.0` instead of `:latest`. The two tags shared one digest when this release was cut, so runtime behaviour is unchanged, but rebuilds are now reproducible and Renovate can propose new Ollaya releases (CUDA tags stay excluded).

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

**From this repository (recommended):** in Home Assistant, open **Settings → Apps → App store** → ⋮ → **Repositories**, add `https://github.com/pier-andre/ollaya-ha-addon` (the repository must stay public: the Supervisor clones it without credentials), then install **Ollaya Decision Models** and start it. The add-on lives in the `ollaya/` folder, whose name is its slug, so Home Assistant installs it as `<hash>_ollaya` with its data in `/data/apps/data/<hash>_ollaya`. Coming from a local `/addons` copy therefore means moving that folder.

**From a local copy (development):** copy **the contents of `ollaya/`** to `/addons/local/ollaya/`, refresh the Home Assistant app store, **rebuild/update** the app image to version `0.1.9`, and restart. A simple restart of the old container will not pick up the translations or Python changes. Existing model data and API keys are not intentionally changed.

Updates are automated by the [Renovate add-on](https://github.com/pier-andre/renovate-ha-addon), which reads `renovate.json` at the root of this repository.

For full installation steps, configuration, and private networking see [English documentation](ollaya/DOCS.md) or [documentation française](ollaya/docs/fr.md).

**Scope:** CPU-only edition for Generic x86-64 Home Assistant OS. The application is based on Ollaya [upstream](https://github.com/ollaya-dev/ollaya) and always runs on the CPU: the device is fixed to `cpu` in `server.py` and the image is the pinned `ghcr.io/ollaya-dev/ollaya:0.18.0` CPU build. The pin is maintained by the Renovate app, so a rebuild no longer changes the runtime silently. GPU acceleration is not packaged and cannot be enabled here; the verified reasons and the conditions for a future GPU edition are in [docs/gpu/README.md](docs/gpu/README.md).

Testing: local automated tests use a simulated Ollaya engine; a real Home Assistant build and bilingual frontend check must still be performed after installation.
