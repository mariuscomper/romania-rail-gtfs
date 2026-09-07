PYTHON ?= python3

.PHONY: build validate test refresh

build:
	$(PYTHON) scripts/build_release.py
	$(PYTHON) scripts/build_atlas.py
	$(PYTHON) scripts/write_manifest.py

refresh:
	$(PYTHON) scripts/fetch_gtfs.py

validate:
	$(PYTHON) scripts/validate.py

test:
	$(PYTHON) -m unittest discover -s tests -v
