# Ollaya Decision Models — Home Assistant app documentation

**English | [Français](docs/fr.md)**

## Purpose and compatibility

Run local Ollaya decision models on Generic x86-64 Home Assistant OS without a GPU. The current app packages the CPU variant of `ghcr.io/ollaya-dev/ollaya:0.18.0`; it does not enable NVIDIA GPU acceleration. The upstream tag is pinned rather than moving, so a rebuild always produces the same runtime, and a new Ollaya release arrives as a Renovate pull request that raises this tag, the app version and the changelog together. CUDA tags are never offered here: this edition is CPU-only.

## Install / upgrade

1. Add `https://github.com/pier-andre/ollaya-ha-addon` as an app repository (⋮ → **Repositories**) and install **Ollaya Decision Models**; for local development, put the `ollaya/` directory's files in `/addons/local/ollaya/` instead. The repository must stay public: the Supervisor clones it without credentials.
2. Refresh the Home Assistant App Store, install or **rebuild/update** the app, and confirm version **0.1.8**.
3. Configure the app; start it and open **Open Web UI** (Home Assistant ingress).
4. Enable **Model management**, save the configuration, and restart the app.
5. Install `laya:en` or another Ollaya-registered model in the web UI. Confirm it appears under Installed models.
6. Disable **Model management** again, save and restart. Installed models can still be selected; inference still runs locally.

**Upgrade safety:** The existing option key is still `model_downloads_enabled`. Only its display name/meaning changes: **both installation and deletion** are blocked when disabled. No manual migration or deletion of `/data/ollaya/` is required.

## Configuration

| Display label | Stored option | Initial value | Details |
|---|---|---|---|
| Default model | `default_model` | `laya:en` | Used when API requests omit the model; an ingress selection overrides until reset. |
| Model management | `model_downloads_enabled` | `false` | Allows installing **and removing** models; keep off between maintenance windows. |
| Keep model loaded | `keep_alive` | `5m` | Time before unloading an idle model. |
| Maximum loaded models | `max_loaded_models` | `1` | Recommended for limited RAM. |
| CPU threads | `threads` | `2` | Tune carefully on shared hardware. |
| Maximum inference queue | `max_queue` | `16` | Limit queued inference work. |
| API key | `api_key` | empty | Empty generates a random persistent key viewable in ingress; custom keys must have at least 16 characters. |

Home Assistant provides native **English and French labels** through `translations/en.yaml` and `translations/fr.yaml`, selected according to the Home Assistant user's language. The separate ingress web UI detects the browser's `Accept-Language` preference and provides an **English / Français** selector, whose choice is saved as a non-sensitive cookie. Home Assistant's language setting and the browser's language are not necessarily the same.

## Models and storage

Ollaya uses the persistent, app-private path `/data/ollaya/models` for downloaded model weights, and `/data/ollaya/` for the generated API key and selected-model override. Supervisor owns `/data/options.json` separately. No previous model files need to be moved for this release.

`laya:en` is the English checkpoint. The `laya` alias downloads both English and multilingual models; `laya:multilingual` is a separate checkpoint. You can pull any model **registered in Ollaya's registry**, not arbitrary Hugging Face repository URLs. Registry pulls contact upstream registry/Hugging Face hosts; inference occurs locally. Disabling model management blocks **the app's installation/removal controls**, but is **not a network firewall** or equivalent to disabling all outbound traffic at OS level.

## Local networking and n8n

- `127.0.0.1:11436` — Ollaya runtime, internal to the container.
- `8099` — authenticated ingress manager. Only requests from Home Assistant's ingress gateway are accepted by the admin server.
- `11435` — authenticated inference proxy, available on the Home Assistant app network. Host/LAN publishing is **disabled by default** (`11435/tcp: null`).
- The external inference API never offers `/api/pull`, `/api/delete`, `/api/create`, or `/api/copy`.

For n8n running as a Home Assistant app, try `http://local-ollaya:11435/api/decide` (check the actual app DNS hostname). Include `Authorization: Bearer <API key>` and JSON `Content-Type`. If a model is omitted, the app injects the currently selected default. For monitoring, an authenticated `GET /health` returns 200 when Ollaya is responsive, otherwise 503.

For n8n outside Home Assistant, publishing 11435 permits LAN access. Keep router ports closed, restrict LAN access with firewall rules, and prefer a VPN if necessary. Home Assistant port mapping alone is **not** an internet-access guarantee.

## Diagnostics and privacy

The ingress dashboard shows runtime version/readiness, model memory load status, aggregate inference successes, errors, timeouts, disconnects, average response duration, and the latest 25 request summaries. Metrics live only in RAM; they reset on restart, and contain no email text, request bodies, or authentication headers. Errors originating from Ollaya during download may remain in the upstream engine's language.

## Troubleshooting

- **After a v0.1.6 upgrade, the app fails with `PermissionError: /usr/local/lib/i18n/en.json`:** update/rebuild to v0.1.7. The translation directory permissions are corrected in the image. Restart alone cannot repair the old image. No model data needs to be removed.

- **Can't install/remove:** Turn on Model management in Home Assistant Configuration and restart. It controls **both** operations.
- **The Home Assistant configuration label stays untranslated:** Refresh the app listing after rebuilding and confirm the correct Home Assistant UI language; the internal option key is intentionally unchanged.
- **Manager opens in the wrong language:** Use English / Français in the top-right corner; the browser-language setting may not match Home Assistant's interface language.
- **502 registry error:** Verify outbound HTTPS/DNS access to Ollaya model registry and Hugging Face while installation is enabled.
- **Model not loaded:** Model installation stores files; first inference may load the model into RAM. Inspect the diagnostics panel.
- **n8n request times out:** Raise its timeout conservatively and limit parallel requests, especially for CPU-only models. On failure, avoid email moves until classification succeeds.

## Limitations

Local automated tests use a mock Ollaya daemon and do not prove the image builds under Home Assistant Supervisor. GPU variants require their own upstream CUDA image and tested Supervisor GPU passthrough; see the repository's `GPU_SUPPORT.md`.
