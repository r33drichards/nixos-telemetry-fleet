#!/usr/bin/env python3
"""Reject broadened agent targets or non-store deployment references."""
import json
import re
import sys

def validate(value):
    if not isinstance(value, dict) or set(value) != {"agents", "rollbackScript"}:
        raise ValueError("Unexpected deployment specification")
    if set(value["agents"]) != {"node2"} or set(value["rollbackScript"]) != {"x86_64-linux"}:
        raise ValueError("Only node2 x86_64-linux is approved")
    store = r"/nix/store/[0-9a-z]{32}-[a-zA-Z0-9+._?=-]+"
    if not re.fullmatch(store, value["agents"]["node2"]):
        raise ValueError("Invalid system closure")
    if not re.fullmatch(store + r"/bin/node2-health", value["rollbackScript"]["x86_64-linux"]):
        raise ValueError("Invalid health-check closure")

if __name__ == "__main__":
    validate(json.load(open(sys.argv[1])))
