#!/usr/bin/env python3
"""Canonical content-and-reference identity for a single Nix runtime closure."""
import base64
import hashlib
import json
import re
import sys

STORE_PATH = re.compile(r"/nix/store/[0123456789abcdfghijklmnpqrsvwxyz]{32}-[a-zA-Z0-9+._?=-]+")
FORBIDDEN = (".drv", "-deploy.json", "-node2-hermes-bootstrap-assets",
             "-node2-health", "-node2-hermes-health")


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate path-info key")
        result[key] = value
    return result


def valid_path(path):
    return (
        isinstance(path, str) and STORE_PATH.fullmatch(path)
        and not path.endswith(FORBIDDEN) and "-nixos-system-" not in path
    )


def canonical(root, info):
    if not valid_path(root) or not isinstance(info, dict) or root not in info:
        raise ValueError("missing or invalid runtime root")
    paths = {}
    for path, entry in info.items():
        if not valid_path(path) or not isinstance(entry, dict):
            raise ValueError("unexpected closure member")
        nar_hash = entry.get("narHash")
        nar_size = entry.get("narSize")
        refs = entry.get("references")
        if not isinstance(nar_hash, str) or not re.fullmatch(r"sha256-[A-Za-z0-9+/]{43}=", nar_hash):
            raise ValueError("invalid NAR hash")
        if len(base64.b64decode(nar_hash[7:], validate=True)) != 32:
            raise ValueError("invalid NAR digest length")
        if type(nar_size) is not int or nar_size <= 0:
            raise ValueError("invalid NAR size")
        if not isinstance(refs, list) or not all(valid_path(ref) and ref in info for ref in refs):
            raise ValueError("invalid or missing reference")
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate store reference")
        paths[path] = {"narHash": nar_hash, "narSize": nar_size, "references": sorted(refs)}
    reachable = set()
    pending = [root]
    while pending:
        path = pending.pop()
        if path not in reachable:
            reachable.add(path)
            pending.extend(paths[path]["references"])
    if reachable != set(paths):
        raise ValueError("closure contains paths not reachable from the runtime root")
    return json.dumps(
        {"version": 1, "root": root, "paths": paths}, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


if __name__ == "__main__":
    try:
        root, = sys.argv[1:]
        info = json.load(sys.stdin, object_pairs_hook=unique_keys)
        print(hashlib.sha256(canonical(root, info)).hexdigest())
    except (ValueError, TypeError) as exc:
        sys.exit(f"Invalid Hermes runtime closure: {exc}")
