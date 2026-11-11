# Édition CPU uniquement : l'application n'active aucun GPU, et le Supervisor ne
# peut de toute façon pas en fournir un sous Home Assistant OS (voir
# docs/gpu/README.md à la racine du dépôt).
# Image upstream épinglée à une version précise.
# `latest` a été abandonné : une reconstruction pouvait changer de moteur sans
# que rien ne le signale, et Renovate ne pouvait rien proposer (une étiquette
# mobile n'a pas de version à comparer). C'est désormais la PR de Renovate qui
# fait avancer ce numéro, avec le `version:` de config.yaml et une ligne de
# CHANGELOG dans la même PR.
# Les variantes GPU doivent utiliser Ollaya `:cuda` ou `:cuda12` : la règle
# `versioning` de renovate.json n'accepte que les étiquettes X.Y.Z, donc les
# images CUDA ne seront jamais proposées pour cette édition.
FROM ghcr.io/ollaya-dev/ollaya:0.18.0
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 gosu \
    && rm -rf /var/lib/apt/lists/*
COPY --chmod=0755 start.sh /usr/local/bin/ollaya-ha-start
COPY --chmod=0644 server.py /usr/local/lib/ollaya-ha-server.py
# Create the i18n directory explicitly. Docker COPY can create a parent
# directory that is inaccessible to the unprivileged Ollaya service account.
RUN install -d -o root -g root -m 0755 /usr/local/lib/i18n
COPY --chown=root:root --chmod=0644 i18n/en.json /usr/local/lib/i18n/en.json
COPY --chown=root:root --chmod=0644 i18n/fr.json /usr/local/lib/i18n/fr.json
# Fail the image build if the real service user cannot traverse the directory,
# open either translation catalog, or parse its JSON content.
RUN chmod 0755 /usr/local/lib/i18n \
    && chmod 0644 /usr/local/lib/i18n/en.json /usr/local/lib/i18n/fr.json \
    && gosu ollaya:ollaya python3 -c 'import json; from pathlib import Path; p=Path("/usr/local/lib/i18n"); catalogs=[json.loads((p / (lang + ".json")).read_text(encoding="utf-8")) for lang in ("en", "fr")]; assert catalogs[0].keys() == catalogs[1].keys()'
ENTRYPOINT ["/usr/local/bin/ollaya-ha-start"]
CMD []
