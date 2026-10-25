SHELL := /usr/bin/env bash
.PHONY: check eval
eval:
	nix flake check --no-build --all-systems
	for node in node1 node2 node3; do nix flake check --no-build "./nodes/$$node"; done
check:
	python3 -m unittest discover -s tests -v
profile-check:
	nix eval --impure --json --file tests/evaluate.nix
vm-e2e:
	nix build -L .#checks.x86_64-linux.boot-overlay-wasm
tf-check:
	terraform -chdir=terraform fmt -check -recursive
	terraform -chdir=terraform init -backend=false -input=false -lockfile=readonly
	terraform -chdir=terraform validate
	terraform -chdir=terraform test
	terraform -chdir=terraform/modules/azure-hosts init -backend=false -input=false -lockfile=readonly
	terraform -chdir=terraform/modules/azure-hosts test
