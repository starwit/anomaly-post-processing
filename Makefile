.PHONY: install build-deb clean check-settings test

export PACKAGE_NAME=anomalypostprocessing

install: check-settings
	poetry install -vvv

check-settings:
	./check_settings.sh

test: install
	poetry run pytest

