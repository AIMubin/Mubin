.PHONY: test curation-queue-plan acquire-sources verify-source-cache build-splits prepare-manifests validate freeze anchor-freeze verify-freeze export-tuning-pack pre-h4-audit

HOLDOUT_KEY ?= /secure/off-repo/mubin-h392.key
FREEZE_ANCHOR ?= /secure/off-repo/mubin-h392-freeze-anchor.json
SOURCE_COMMIT ?= $(shell git rev-parse HEAD)

test:
	python -m unittest discover -s tests -v

curation-queue-plan:
	python -m benchmark_campaign curation-queue-plan

acquire-sources:
	python -m benchmark_campaign acquire-sources

verify-source-cache:
	python -m benchmark_campaign verify-source-cache

build-splits:
	python -m benchmark_campaign build-splits --holdout-key-file $(HOLDOUT_KEY)

prepare-manifests:
	python -m benchmark_campaign prepare-manifests

validate:
	python -m benchmark_campaign validate

freeze:
	python -m benchmark_campaign freeze

anchor-freeze:
	python -m benchmark_campaign anchor-freeze --anchor-file $(FREEZE_ANCHOR) --source-commit $(SOURCE_COMMIT)

verify-freeze:
	python -m benchmark_campaign verify-freeze --anchor-file $(FREEZE_ANCHOR)

export-tuning-pack:
	python -m benchmark_campaign export-tuning-pack

pre-h4-audit:
	python -m benchmark_campaign pre-h4-audit
