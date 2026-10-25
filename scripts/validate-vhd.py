#!/usr/bin/env python3
"""Validate the actual fixed VHD footer, GPT and host-specific content report."""
import hashlib
import json
import pathlib
import struct
import sys

path = pathlib.Path(sys.argv[1])
with path.open('rb') as stream:
    stream.seek(-512, 2)
    footer = stream.read(512)
    assert footer[:8] == b'conectix', 'Missing VHD footer'
    assert struct.unpack('>I', footer[60:64])[0] == 2, 'VHD must be fixed, not dynamic'
    virtual_size = struct.unpack('>Q', footer[48:56])[0]
    assert virtual_size % (1024 * 1024) == 0, 'Azure disk size must be MiB aligned'
    assert path.stat().st_size == virtual_size + 512, 'Fixed VHD length mismatch'
    checksum = struct.unpack('>I', footer[64:68])[0]
    assert checksum == (~sum(footer[:64] + b'\0' * 4 + footer[68:]) & 0xffffffff), 'Invalid footer checksum'
    stream.seek(512)
    assert stream.read(8) == b'EFI PART', 'Expected GPT disk for Gen2'
    stream.seek(0)
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
print(json.dumps({'file': path.name, 'format': 'fixed-vhd', 'partition_table': 'GPT', 'virtual_bytes': virtual_size, 'sha256': digest, 'azure_boot_tested': False}))
