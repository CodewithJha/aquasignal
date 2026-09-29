#!/usr/bin/env bash
# Manual / release-time only — NOT part of pytest or CI. Needs network, Node (npx),
# and Java 17+ or Docker.
#
# Validates exported Bundles against the hl7-eu/oah IG with the official HL7 validator.
# No built OAH package is published (build.fhir.org CI build and packages.fhir.org
# both return 404), so the IG is compiled from FSH at a pinned commit with SUSHI.
#
# Usage: scripts/validate_fhir.sh bundle.json [bundle2.json ...]
#   (get a bundle with: curl "http://localhost:8000/fhir/bundle?packet_id=<id>" -o bundle.json)
set -euo pipefail

OAH_COMMIT="${OAH_COMMIT:-b907cf0869b59d82d9138b3d147fca66f333d911}"
SUSHI_VERSION="${SUSHI_VERSION:-3.20.1}"
WORK="${FHIR_VALIDATION_DIR:-/tmp/fhir-validation}"
JAR_URL="https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar"

[ "$#" -ge 1 ] || { echo "usage: $0 bundle.json [...]" >&2; exit 2; }
mkdir -p "$WORK/inputs" "$WORK/fhir-cache"
inputs=()
for f in "$@"; do
  cp "$f" "$WORK/inputs/$(basename "$f")"
  inputs+=("/work/inputs/$(basename "$f")")
done

[ -f "$WORK/validator_cli.jar" ] || curl -fsSL -o "$WORK/validator_cli.jar" "$JAR_URL"

if [ ! -d "$WORK/oah-ig/.git" ]; then
  git clone -q https://github.com/hl7-eu/oah.git "$WORK/oah-ig"
fi
git -C "$WORK/oah-ig" fetch -q origin
git -C "$WORK/oah-ig" checkout -q "$OAH_COMMIT"
(cd "$WORK/oah-ig" && npx -y "fsh-sushi@$SUSHI_VERSION" build . >/dev/null)

args=("${inputs[@]}" -version 4.0.1
  -ig /work/oah-ig/fsh-generated/resources
  -ig "hl7.fhir.uv.xver-r5.r4#0.1.0"
  -output /work/out.json)

if command -v java >/dev/null 2>&1 && java -version >/dev/null 2>&1; then
  (cd "$WORK" && java -jar validator_cli.jar "${args[@]//\/work/$WORK}")
else
  docker run --rm -v "$WORK:/work" -v "$WORK/fhir-cache:/root/.fhir" -w /work \
    eclipse-temurin:21-jre java -jar validator_cli.jar "${args[@]}"
fi
echo "OperationOutcome written to $WORK/out.json"
