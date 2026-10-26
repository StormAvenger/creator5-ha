"""Bounded sliced-file validation. No extraction, execution or G-code generation."""

import codecs
import re
import stat
import zipfile
import zlib
from pathlib import PurePosixPath
from typing import BinaryIO

MAX_UPLOAD = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024


def file_name(value: object) -> str:
    """Allow a single printable basename, never a path, URL or header injection."""
    if (
        not isinstance(value, str)
        or not 1 <= len(value.encode("utf-8")) <= 200
        or value != value.strip()
        or value.startswith(".")
        or any(ord(c) < 32 or ord(c) == 127 or c in '/\\:"<>|?*' for c in value)
        or not value.lower().endswith((".3mf", ".gcode"))
    ):
        raise ValueError("Choose a sliced .3mf or .gcode file with a plain filename")
    return value


def upload_name(value: str, identifier: str) -> str:
    """Use a unique printer filename so uploads do not replace a user's file."""
    file_name(value)
    stem, extension = value.rsplit(".", 1)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-")[:60] or "print"
    return file_name(f"{stem}-{identifier}.{extension.lower()}")


def validate_slice(stream: BinaryIO, name: str) -> int:
    """Check structure/size, not machine compatibility or physical print safety."""
    file_name(name)
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if not 0 < size <= MAX_UPLOAD:
        raise ValueError("Sliced files must be nonempty and at most 64 MiB")
    if name.lower().endswith(".3mf"):
        try:
            with zipfile.ZipFile(stream) as archive:
                entries = archive.infolist()
                if not entries or len(entries) > 4096:
                    raise ValueError("Unsupported 3MF archive")
                expanded = 0
                gcode = False
                names = set()
                for item in entries:
                    path = PurePosixPath(item.filename)
                    expanded += item.file_size
                    if (
                        item.filename in names
                        or path.is_absolute()
                        or ".." in path.parts
                        or "\\" in item.filename
                        or ":" in item.filename
                        or any(ord(c) < 32 for c in item.filename)
                        or stat.S_ISLNK(item.external_attr >> 16)
                        or item.flag_bits & 1
                        or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or expanded > MAX_EXPANDED
                    ):
                        raise ValueError("Unsupported or unsafe 3MF archive")
                    names.add(item.filename)
                    if not item.is_dir():
                        # Read through for CRC/integrity checks without extracting any files.
                        with archive.open(item) as source:
                            while source.read(1024 * 1024):
                                pass
                        gcode |= item.filename.lower().endswith(".gcode") and item.file_size > 0
                if not gcode:
                    raise ValueError("Upload a sliced 3MF containing G-code, not an unsliced model")
        except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, OSError):
            raise ValueError("Invalid or unsupported sliced 3MF archive") from None
    else:
        decoder = codecs.getincrementaldecoder("utf-8")()
        try:
            while chunk := stream.read(1024 * 1024):
                text = decoder.decode(chunk)
                if any(ord(c) < 32 and c not in "\t\r\n" for c in text):
                    raise ValueError("G-code must be a text file")
            decoder.decode(b"", final=True)
        except UnicodeError:
            raise ValueError("G-code must be a UTF-8 text file") from None
    stream.seek(0)
    return size
