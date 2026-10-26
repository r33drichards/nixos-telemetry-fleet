SHELL := /usr/bin/env bash
.PHONY: check eval
eval:
	# Materialize the pinned upstream filtered source before read-only flake checking.
	# Nix --no-build otherwise computes its store path without writing it.
	nix eval --raw .#nixosConfigurations.node2-hermes.config.system.build.toplevel.drvPath --no-update-lock-file >/dev/null
	nix flake check --no-build --all-systems
	for node in node1 node2 node3; do nix flake check --no-build "./nodes/$$node"; done
check:
	python3 -m unittest discover -s tests -v
profile-check:
	nix eval --impure --json --file tests/evaluate.nix
vm-e2e:
	nix build -L .#checks.x86_64-linux.boot-ssh-comin
tf-check:
	terraform -chdir=terraform fmt -check -recursive
	terraform -chdir=terraform init -backend=false -input=false -lockfile=readonly
	terraform -chdir=terraform validate
	terraform -chdir=terraform test
	terraform -chdir=terraform/modules/azure-hosts init -backend=false -input=false -lockfile=readonly
	terraform -chdir=terraform/modules/azure-hosts test
	terraform -chdir=terraform/amd-canary init -backend=false -input=false -lockfile=readonly
	terraform -chdir=terraform/amd-canary validate
	terraform -chdir=terraform/amd-canary test
