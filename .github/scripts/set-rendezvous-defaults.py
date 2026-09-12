#!/usr/bin/env python3
"""Replace only the two default literals in a disposable CI checkout."""

import base64
import binascii
import ipaddress
import os
from pathlib import Path
import re
import sys


def main():
    server = os.environ.get("RENDEZVOUS_SERVER", "")
    key = os.environ.get("RS_PUB_KEY", "")
    label = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    if not (0 < len(server) <= 253 and
            re.fullmatch(label + r"(?:\." + label + r")+", server)):
        raise ValueError("RENDEZVOUS_SERVER must be a DNS hostname or IPv4 address")
    if re.fullmatch(r"[0-9.]+", server):
        try:
            ipaddress.IPv4Address(server)
        except ValueError:
            raise ValueError("RENDEZVOUS_SERVER is not a valid IPv4 address") from None
    try:
        decoded = base64.b64decode(key, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("RS_PUB_KEY must be canonical Base64 for 32 bytes") from None
    if len(decoded) != 32 or base64.b64encode(decoded).decode("ascii") != key:
        raise ValueError("RS_PUB_KEY must be canonical Base64 for 32 bytes")

    path = Path("libs/hbb_common/src/config.rs")
    source = path.read_bytes()
    patterns = (
        (b"RENDEZVOUS_SERVERS",
         rb'^pub const RENDEZVOUS_SERVERS: &\[&str\] = (&\["[^"\r\n]*"\]);\r?$',
         ('&["' + server + '"]').encode("ascii")),
        (b"RS_PUB_KEY",
         rb'^pub const RS_PUB_KEY: &str = ("[^"\r\n]*");\r?$',
         ('"' + key + '"').encode("ascii")),
    )
    edits = []
    for name, pattern, replacement in patterns:
        declarations = re.findall(rb"\bpub\s+const\s+" + name + rb"\b", source)
        matches = list(re.finditer(pattern, source, re.MULTILINE))
        if len(declarations) != 1 or len(matches) != 1:
            raise ValueError("Expected exactly one supported declaration per default constant")
        edits.append((*matches[0].span(1), replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    path.write_bytes(source)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError):
        # Never include input values or source contents in CI logs.
        print("Default server configuration failed validation or could not be written.", file=sys.stderr)
        sys.exit(1)
