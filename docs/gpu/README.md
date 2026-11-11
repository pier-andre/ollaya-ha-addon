# GPU / CUDA notes: why this app is CPU-only

**English | [Français](#résumé-en-français)**

This folder is reference material, not an app. The Home Assistant app in this
repository is `ollaya/`, and it is a **CPU-only edition**: the device is fixed
to `cpu` in `ollaya/server.py` (`DEVICE = "cpu"`, exported as
`OLLAYA_DEVICE`), the base image is the CPU build
`ghcr.io/ollaya-dev/ollaya:0.18.0`, and no GPU option exists in the settings.
The startup log says so on every boot.

Nothing here is a promise of a future feature. It records why CUDA cannot work
under Home Assistant OS today, and what would have to change for a GPU edition
to be worth building.

## The upstream CUDA images are fine; the Home Assistant packaging is not

Upstream Ollaya publishes Linux amd64 CUDA variants:

| Tag | Stack | Host driver | Compressed size (0.18.0) |
|---|---|---|---|
| `ghcr.io/ollaya-dev/ollaya:cuda` | CUDA 13 | R580 or newer | ~1643 MiB |
| `ghcr.io/ollaya-dev/ollaya:cuda12` | CUDA 12 | R525 or newer (also Pascal/Volta) | ~2251 MiB |

Both are also published as immutable `X.Y.Z-cuda` / `X.Y.Z-cuda12` tags, which
is what an edition would pin. Their image configuration sets
`NVIDIA_VISIBLE_DEVICES=all` and `NVIDIA_DRIVER_CAPABILITIES=compute,utility`,
runs as user `1000:1000` and exposes `OLLAYA_DEVICE` with
`auto` (default), `cpu`, `cuda` or `cuda:<n>`.

Those environment variables are **hints for the NVIDIA Container Toolkit**, not
a driver. In plain Docker they only work when the host has the proprietary
driver plus the toolkit and the container is started with `--gpus all`. That is
the case where upstream CUDA is known to work, and it is not Home Assistant.

## The three blockers on Home Assistant

**1. Home Assistant OS ships no NVIDIA driver.** Accelerator support in HAOS is
limited to specific, officially integrated devices (Coral, Hailo). There is no
proprietary NVIDIA kernel module and no `libcuda.so` on the host for a container
to use. This is the same reason Frigate's NVIDIA hardware acceleration does not
work on HAOS: the maintainers state plainly that NVIDIA is unsupported there
because the driver cannot be installed.

**2. The Supervisor cannot request a GPU.** An app's configuration schema only
offers `devices`, `full_access`, `uart`, `usb`, `gpio`, `video` and
`host_uts`. There is no equivalent of `--gpus all` and no way to select the
`nvidia` container runtime. Even a Supervised install (Debian host with drivers
and toolkit installed) cannot be told by an app to inject them; the effective
technique is `full_access: true` plus explicit `/dev/nvidia*` device mappings,
which is undocumented for apps, unverified here, and unsupported by Home
Assistant.

**3. Device nodes alone do not create a CUDA device.** Mapping `/dev/nvidia0`
does not inject `libcuda.so`, the driver libraries matching the image's CUDA
version, or the correct permissions. The privileged container would still find
no usable GPU.

### Why a CUDA build is not shipped anyway

The CUDA image starts without a GPU and falls back to a CPU runner, logging
`GPU runtime not installed, using CPU: no CUDA runtime in <folder>`. On HAOS
that fallback would be permanent. The result would be an app that is roughly
2.2 GiB larger, slower to start, visually identical to the CPU edition, and
accelerating nothing, while claiming GPU support in its name. That is the
misleading packaging this repository avoids; hence one CPU app and this
reference note.

## When it can and cannot work

| Installation type | NVIDIA GPU usable by the app? | What is missing |
|---|---|---|
| Home Assistant OS (this app's target) | No | No NVIDIA driver shipped; Supervisor cannot set the runtime or `--gpus` |
| Home Assistant Supervised | Possibly, unverified | Host drivers + NVIDIA Container Toolkit + `full_access: true` and `/dev/nvidia*` mappings; not supported by Home Assistant |
| Home Assistant Container (Core in Docker) | Possibly, same as Supervised | Same, configured manually on the host |
| Ollaya in plain Docker, outside Home Assistant | Yes | `--gpus all` with driver and toolkit; upstream's supported path |

No NVIDIA hardware was available while this app was written, so **none of the
GPU paths above were tested here**. Treat the "possibly" rows as untested.

AMD/Intel GPUs should not be promised from Ollaya's `/dev/dri` mapping alone:
confirm upstream backends first, as their ROCm support was still under
development. The same Supervisor and driver caveats apply.

## What a GPU edition would need, in order

1. **Pick the target.** An HAOS-compatible app is not possible today; the
   honest scope is an experimental Supervised/Container build, or no GPU app at
   all. Do not advertise acceleration on HAOS.
2. **Prove the image boots without a GPU** (do this first, on ordinary
   hardware): `docker run --rm ghcr.io/ollaya-dev/ollaya:0.18.0-cuda12
   ollaya --version`, then `serve`, and confirm the CPU-fallback log line.
3. **Package it as a second app folder** in this repository (`ollaya-cuda/`)
   rather than a second repository: an app's build context is its own folder,
   so the shared files are copied either way, but one repository keeps one
   Renovate config, one changelog script and one test suite. Splitting later is
   a `git mv`; the reverse merge is the painful direction.
4. **Change four things in the copy:** `FROM ghcr.io/ollaya-dev/ollaya:<X.Y.Z>-cuda12`,
   a `device` option (`auto` / `cpu` / `cuda`) feeding `OLLAYA_DEVICE` instead
   of the hardcoded constant, a startup line naming the device actually chosen,
   and a distinct slug so it gets a fresh `/data` (downloaded model files are
   portable between editions and only need copying).
5. **Keep Renovate honest.** The current rule in `renovate.json` matches
   `ghcr.io/ollaya-dev/ollaya` with a versioning regex that accepts only
   `X.Y.Z`, which would suppress every `-cuda12` bump. The GPU folder needs its
   own rule (for example `matchFileNames: ["ollaya-cuda/Dockerfile"]`) with a
   regex accepting `X.Y.Z-cuda12`, placed so it wins over the CPU rule: later
   `packageRules` entries take precedence.
6. **Validate what can be validated without a GPU:** image build and start,
   option-to-environment plumbing, the visible fallback log, download and
   inference still working, CPU app untouched, and both editions installable
   side by side.
7. **Find one tester with an NVIDIA card** before the edition is described as
   accelerated. Until someone reports `nvidia-smi` working and a GPU runner in
   the Ollaya logs inside the container, the status is "unverified". The
   remaining validation list: model load/unload, deterministic decisions versus
   CPU, restart behaviour, memory usage, older drivers and GPUs.

For any public GPU edition: add a description that says which install types it
supports, a CI build matrix, a support policy, and the same bilingual docs used
by the CPU app. Never publish the model manager or inference port by default.

## Résumé en français

Ce dossier est une note de référence, pas une application. L’application de ce
dépôt (`ollaya/`) est **réservée au CPU** : `OLLAYA_DEVICE=cpu` est fixé dans
`ollaya/server.py`, l’image de base est `ghcr.io/ollaya-dev/ollaya:0.18.0`
(édition CPU) et aucune option GPU n’existe. Le journal de démarrage l’indique.

Les images CUDA d’Ollaya (`:cuda` CUDA 13 / R580+, `:cuda12` CUDA 12 / R525+)
fonctionnent hors de Home Assistant avec `--gpus all`. Sous Home Assistant,
trois obstacles s’y opposent : Home Assistant OS ne fournit aucun pilote NVIDIA,
le Supervisor ne peut pas demander de GPU (aucun équivalent de `--gpus all` ni du
runtime `nvidia`, seulement `devices` et `full_access`), et mapper `/dev/nvidia0`
n’injecte ni `libcuda.so` ni les bibliothèques du pilote. Une image CUDA
démarre donc sans GPU et retombe définitivement sur le CPU, en étant environ
2,2 Gio plus lourde : c’est exactement l’emballage trompeur que cette édition
évite.

Une édition GPU éventuelle viserait Supervised/Container (non testé, non pris en
charge par Home Assistant), devrait changer le `FROM`, remplacer la constante
`DEVICE` par une option `auto`/`cpu`/`cuda`, consigner le périphérique retenu,
utiliser un identifiant propre (donc un `/data` neuf) et ajouter une règle
Renovate dédiée acceptant les étiquettes `X.Y.Z-cuda12`. Aucune accélération ne
peut être vérifiée ici : cela demande un testeur disposant d’une carte NVIDIA.
