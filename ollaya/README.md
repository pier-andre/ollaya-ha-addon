# Ollaya Decision Models for Home Assistant OS (CPU-only edition)

**English | [Français](docs/fr.md)**

For the updated Home Assistant 0.1.7 bilingual instructions, see [DOCS.md](DOCS.md) or [documentation française](docs/fr.md).

**Target:** Home Assistant OS, x86-64, CPU only, including 8 GB RAM systems. This app never uses a GPU: `OLLAYA_DEVICE=cpu` is fixed in `server.py` and the startup log says so. **Tested on:** one Home Assistant OS setup; not broadly validated.

## Install

**From the repository (recommended):** in **Settings > Apps > App store**, open ⋮ → **Repositories**, add `https://github.com/pier-andre/ollaya-ha-addon`, reload, install **Ollaya Decision Models**, and start it. The repository must stay public: the Supervisor clones it without credentials. The add-on lives in the `ollaya/` folder, whose name is its slug, so Home Assistant installs it as `<hash>_ollaya`.

**From a local copy (development):** copy the `ollaya/` folder into `/addons/local/ollaya/` using your preferred Home Assistant file-access mechanism. In **Settings > Apps > App store**, use **Check for updates / Reload**, install **Ollaya Decision Models**, and start it.

The initial build uses the published upstream Ollaya CPU container. Docker/HA Supervisor downloads the container image to install the app.

Use **Open Web UI** to access the model manager via Home Assistant ingress. The model manager is restricted to the ingress gateway address, and Home Assistant authenticates ingress users. It is not hosted on your public LAN port.

1. In **Configuration**, leave `default_model: laya:en`, `max_loaded_models: 1`, `keep_alive: 5m`, and `threads: 2` to start. Keep the default API host-port mapping **disabled**.
2. Temporarily enable `model_downloads_enabled`, save and restart.
3. In the ingress UI, click **Pull** for `laya:en`, watching the progress page. The weights are downloaded from Hugging Face as specified by Ollaya's registry, with sha256 verification.
4. When the pull is complete, disable **Model management** (`model_downloads_enabled`), save and restart. Inference is local and requires no internet connectivity once the model is installed.
5. For a different default, select one of the *installed* models in the ingress UI (runtime override), or edit `default_model` in HA Configuration. Click **Reset override** to return to the HA Configuration value.

## Persistent model storage

Home Assistant Supervisor gives each app its own writable `/data` volume. This
app keeps Ollaya model weights in **`/data/ollaya/models`** and stores its
selected-model override and generated API key under `/data/ollaya/`. Both survive
container restarts and app image updates; the paths belong to **this Ollaya app**
and are distinct from another app's `/data/ollama` folder.

`/data/options.json` is a separate Home Assistant Supervisor-managed file and
may be root-only (`0600`). The startup script stages a private read-only copy in
`/run/ollaya-ha/options.json` before switching to the unprivileged `ollaya`
account. It never changes permissions on the Supervisor configuration file.

The Ollaya daemon receives `OLLAYA_MODELS=/data/ollaya/models` explicitly. The
startup script creates the directories with ownership `ollaya:ollaya` and mode
`0700`; it does not recursively change permissions of downloaded models on
subsequent boots. The ingress model manager displays the active storage path.

## API/network access

- Internal Ollaya daemon: `127.0.0.1:11436` within the container, not accessible from other apps.
- Filtered, API-key-protected inference proxy: port `11435` *within the Home Assistant app network*. The proxy permits decision and read-only model status calls. It **never exposes `/api/pull`, `/api/delete`, `/api/create`, or `/api/copy`**, regardless of download setting.
- Model manager: port `8099`, reachable **only from the Home Assistant ingress gateway (172.30.32.2)**, behind HA authentication.
- Host port mapping for `11435/tcp` defaults to `null` (disabled). Keep it disabled for n8n running as a HA app. Use the app's DNS hostname: `http://local-ollaya:11435` if installed locally, or the generated `<repository>-ollaya` hostname if installed from a remote repository. See HA app communication documentation.
- If n8n runs on another computer, optionally publish `11435` on your LAN; **HA port mapping alone does not guarantee WAN isolation**. Restrict access with your router/firewall, do not create port forwards or expose via reverse proxies, and always use an API key. Consider a private VPN instead.
- API key: leave HA `api_key` blank to auto-generate a random key in `/data/ollaya/api_key`, shown inside the authenticated ingress UI. Or set your own key in the HA Configuration and restart. No key is printed in the addon logs.

Example n8n HTTP Request node:

- Method: POST
- URL: `http://local-ollaya:11435/api/decide` (adjust DNS hostname)
- Header: `Authorization: Bearer <generated key>`
- Header: `Content-Type: application/json`
- JSON body: `{ "state": "The order shipped", "questions": { "kind": { "type": "choice", "criteria": { "important": "Requires action", "routine": "Routine notification" } } } }`
- `model` can be omitted to use the app-selected default; or supply a specific installed model such as `laya:en`.

## Model names and Hugging Face

- `laya:en` is the English-only Laya checkpoint; **`laya` is a language router** and downloads `laya:en` plus `laya:multilingual`.
- The model manager lists locally installed models and offers registered model names with a free-text input. Only Ollaya-registered models (or supported custom registry entries) can be pulled. Arbitrary Hugging Face model repositories are **not** directly importable.
- Downloads contact Ollaya's model registry and the model authors' Hugging Face repositories; inference sends no content to an external model service.
- `model_downloads_enabled=false` blocks both pulling and deleting from the manager, and the external API never exposes model-management mutations. This is an **application-level download gate, not an operating-system network egress firewall**. For strict no-egress assurance, enforce outbound network restrictions externally after downloading models.

## RAM and CPU

With 8 GB host RAM, use `laya:en` first, `max_loaded_models: 1`, and keep-alive of `5m` (or `1m` if Home Assistant is memory-constrained). Start with 2 threads and observe host load and the actual resident memory reported by Ollaya. CPU inference uses FP32 for Laya; the model's download size is **not** its RAM requirement. `laya:en` has a 512-token context: keep prompts short, or handle `STATE_TRUNCATED` rather than altering or discarding critical information.

## Maintenance and limitations

- This CPU prototype intentionally builds against `ghcr.io/ollaya-dev/ollaya:latest`, as requested. Rebuilds may change the upstream Ollaya runtime version.
- App version is independent of Ollaya runtime version.
- No true per-process outbound firewall is implemented. Download control applies to the exposed interfaces and manager; other outbound behavior from the upstream process is not separately sandboxed.
- UI override persisted in `/data/ollaya/selected_model.txt` takes precedence over `default_model` after an add-on restart until Reset override is pressed.
- The upstream model registry and model availability can change; pull failures are reported in the manager.
- This is not the Ollama Home Assistant integration and does not expose `/api/chat` or generate text.
- This prototype has not been Docker-built or run on Home Assistant OS here. Perform an initial manual install and a dry-run n8n workflow before allowing email mutations.

## v0.1.1 startup permission fix

Home Assistant Supervisor owns `/data/options.json` as `root` and normally
sets its permissions to `0600`. Earlier v0.1.0 dropped privileges before
reading this file and failed with `PermissionError` on first start.

The startup script now reads it while root and stages a copy at
`/run/ollaya-ha/options.json` with `root:ollaya` ownership and `0640`
permissions, in a root-owned `0750` directory. The Python proxy and the Ollaya
daemon still run as the unprivileged `ollaya` account. It does **not** change
the permissions of the Supervisor-managed file. This staged copy is replaced
on every app start after an options change.

To upgrade an app installed from this repository, use **Update** in the App Store: the image is rebuilt. To upgrade a locally installed copy, replace the files in
`/addons/local/ollaya/`, refresh the Home Assistant App Store, confirm the app
version increased, rebuild/reinstall or update the app, then start it. A mere
restart of the v0.1.0 container will not incorporate Dockerfile or script
changes: the container image must be rebuilt. No persistent model data is
removed by updating this package.

## v0.1.2 storage clarification and startup improvement

- Explicitly creates `/data/ollaya` and `/data/ollaya/models` as private,
  service-owned persistent directories.
- Avoids recursively `chown`-ing potentially large model directories at every
  restart.
- Shows the active model storage directory in ingress and logs its path at
  startup (no credentials).
- Adds a startup regression test to verify write access and persistence across
  two runs.

Update the local app files, refresh the App Store, confirm the new version,
then update/rebuild the app image. A simple restart of an earlier image is not
enough to apply changes to `start.sh` or `server.py`. Existing models and
settings under `/data/ollaya` are not deleted by this upgrade.

## v0.1.3 ingress POST fix

The model-manager uses small HTML form requests and now sets `ingress_stream: false`.
Home Assistant can forward streamed ingress POST requests with `Transfer-Encoding: chunked`
which does not include a `Content-Length` header. The Python handler now also accepts
well-formed, size-limited chunked bodies. Both select-list and custom-model pull
forms use the same corrected handler. Changes to `config.yaml` require updating or
rebuilding the app image through Home Assistant; a simple restart is not sufficient.

## v0.1.4 model download diagnostics and direct loopback HTTP

- Uses `http.client.HTTPConnection` for communication with the Ollaya daemon
  on `127.0.0.1:11436`, bypassing any `HTTP_PROXY` that may be configured for
  external access. This does not bypass a proxy that Ollaya itself uses for
  outbound model-registry or Hugging Face downloads.
- Displays a failing upstream response's HTTP status, `code` and `error`,
  for example `Ollaya HTTP 502 (REGISTRY_ERROR): registry DNS lookup failed`.
- Handles JSON error records emitted mid-download, including
  `DIGEST_MISMATCH`, and requires Ollaya's final `status: success` marker.
- Reports failures to the Home Assistant app log in addition to the ingress UI.
- Adds regression tests for proxy interference, HTTP 502, streamed checksum
  failures and incomplete progress streams.

**If you see `REGISTRY_ERROR`:** A direct Ollaya registry access problem remains;
check that the Home Assistant host/container can resolve and reach
`ollaya.dev` over HTTPS, and reach the Hugging Face download hosts used by the
chosen model. `model_downloads_enabled` must be enabled while pulling. A
`DIGEST_MISMATCH` may be retried. Those error codes are defined by upstream
Ollaya's API reference: https://ollaya.dev/docs/api.

**Upgrade:** Copy `ollaya/` over the local app's directory, refresh the App
Store, confirm version `0.1.4`, update/rebuild the image, then restart. App
storage in `/data/ollaya` and the configuration are not intentionally modified.


## v0.1.5 operational diagnostics

The ingress model manager includes Ollaya runtime readiness, recent inference latency and
HTTP status, disconnect/timeout counts, and a rolling list of the 25 most recent
inference requests. These counters are in RAM and reset when the app restarts.
They intentionally contain no email bodies, prompts, authorization headers, or API keys.

For authenticated monitoring, query `GET /health` at the inference API port
with `Authorization: Bearer <API key>`; returns JSON `status: ready` (200) or
`status: unavailable` (503). The root endpoint still indicates only that the proxy listens.

`ghcr.io/ollaya-dev/ollaya:latest` is deliberately kept as the image base. A rebuild
may bring in an untested upstream release; record the Ollaya version when troubleshooting.

GPU support is **not** enabled in this CPU-only app. Read
[`../docs/gpu/README.md`](../docs/gpu/README.md) for why CUDA cannot work on Home
Assistant OS, and for the conditions and steps a GPU edition would need.

## v0.1.7 bilingual model management

- The existing option key `model_downloads_enabled` is now presented as **Model management / Gestion des modèles** through Home Assistant native translation files. Its stored name stays unchanged for upgrades.
- When disabled, both installing and removing models are prevented in the server and hidden from the UI. Installed models are still selectable.
- The ingress manager now supports English and French via browser language detection and manual selection. A non-sensitive language preference cookie survives reloads.
- Detailed docs: [English](DOCS.md) and [Français](docs/fr.md).

## v0.1.7 startup localization fix

Static translation catalogs now live in a pre-created world-traversable application directory. A Docker build-time smoke test loads both JSON catalogs as the unprivileged `ollaya` user. This fixes the permission error seen in Home Assistant after v0.1.6. Existing models and configuration are unchanged.
