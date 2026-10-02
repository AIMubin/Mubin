.PHONY: test curation-queue-plan acquire-sources verify-source-cache build-splits prepare-manifests validate freeze verify-freeze export-tuning-pack pre-h4-audit

HOLDOUT_KEY ?= /secure/off-repo/mubin-m392.key

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

verify-freeze:
	python -m benchmark_campaign verify-freeze

export-tuning-pack:
	python -m benchmark_campaign export-tuning-pack

pre-h4-audit:
	python -m benchmark_campaign pre-h4-audit
