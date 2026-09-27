PYTHON ?= python3
EVIDENCE_DIR ?= /tmp/desktop-workspace-integration

.PHONY: help check check-source test integration stage install pins
help:
	@echo 'check: validate pins and run all source checks'
	@echo 'integration: test placement and HUD in disposable GNOME sessions'
	@echo 'stage: package the pinned public components without installation'
	@echo 'install: stage and schedule installation for next graphical login'
	@echo 'pins: print the recorded component commits'

pins:
	$(PYTHON) scripts/workspace.py pins

check:
	$(PYTHON) scripts/workspace.py check
	$(PYTHON) .github/scripts/privacy.py --index
	$(MAKE) test check-source

# Works in the complete release source archive as well as a recursive clone.
check-source:
	$(MAKE) -C workspace-state check
	node workspace-state/tests/test_edge_policy.mjs
	$(MAKE) -C gnome-winctl test
	$(MAKE) -C login-hud release-artifacts
	$(MAKE) -C input-source-popup-guard check test
	$(MAKE) -C hide-suspend check
	cd gc-profiled && $(PYTHON) -m compileall -q gc_profiled.py scripts tests
	cd gc-profiled && $(PYTHON) -m unittest discover -s tests -v

test:
	$(PYTHON) -m unittest discover -s tests -v

integration:
	$(PYTHON) scripts/workspace.py check
	$(PYTHON) workspace-state/tests/integration/run_headless.py --run --output "$(EVIDENCE_DIR)/placement"
	$(PYTHON) workspace-state/tests/integration/run_hud_headless.py --run --output "$(EVIDENCE_DIR)/hud"

stage:
	$(PYTHON) scripts/workspace.py stage

install:
	$(PYTHON) scripts/workspace.py deploy
