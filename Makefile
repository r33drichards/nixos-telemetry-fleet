SHELL := /usr/bin/env bash
.PHONY: check eval
eval:
	nix flake check --no-build --all-systems
	for node in node1 node2 node3; do nix flake check --no-build "./nodes/$$node"; done
check:
	python3 -m unittest discover -s tests -v
profile-check:
	nix eval --impure --json --file tests/evaluate.nix
