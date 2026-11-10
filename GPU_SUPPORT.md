# GPU edition roadmap (not enabled in v0.1.5)

Upstream Ollaya already provides Linux amd64 NVIDIA CUDA variants:

- `ghcr.io/ollaya-dev/ollaya:cuda`: CUDA 13 stack, generally R580+ host drivers.
- `ghcr.io/ollaya-dev/ollaya:cuda12`: CUDA 12 stack, generally R525+, and
  certain older Pascal/Volta GPUs even with a newer driver.
- `ghcr.io/ollaya-dev/ollaya:latest`: CPU base, unchanged in this edition.

## What is missing from this Home Assistant packaging

1. A GPU-specific Dockerfile/build or published app image based on the appropriate
   upstream CUDA tag (the CPU image cannot gain CUDA just by mapping devices).
2. Home Assistant Supervisor GPU passthrough analogous to the Ollama app's
   `gpus: all`; validate Supervisor, host NVIDIA drivers, NVIDIA Container Toolkit,
   GPU discovery and permission behavior on actual Home Assistant OS hardware.
3. Remove the hardcoded `OLLAYA_DEVICE=cpu` in the GPU edition; expose
   `auto`, `cpu` and supported CUDA selectors in its settings. Ensure CPU fallback
   is logged and visible so users know whether acceleration is used.
4. A multi-variant release strategy for CPU, CUDA 13 and CUDA 12. Home Assistant
   cannot change a Dockerfile `FROM` by toggling a runtime option. A dedicated
   GPU app or documented alternate builds are simpler than pretending an
   inference setting selects the right CUDA container.
5. Validation: CPU fallback with no GPU; `laya:en` GPU selection, deterministic
   decisions vs CPU, load/unload, restart, downloads and n8n request tests;
   older drivers and GPUs; hardware memory usage; protected-port access.

AMD/Intel Linux GPU support should not be promised on the strength of Ollama's
`/dev/dri` and `/dev/kfd` mappings alone. Confirm upstream Ollaya support for
that backend first; upstream's ROCm support is still under development.

For a public repository, also add a LICENSE, CI build matrix, support policy,
versioned changelog, screenshots, security disclosure, and installation guide.
Do not expose the model manager or inference port publicly by default.
