from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


FORMAT_NAME = "fantasy-wars-locdata-v1"
PathLike = Union[str, Path]
INDEX_SIZE = 0x20000
NODE_SIZE = 100
NODE_COUNT = 10240
POOL_HEADER_OFFSET = INDEX_SIZE + NODE_SIZE * NODE_COUNT
POOL_DATA_OFFSET = POOL_HEADER_OFFSET + 16
KEY_XOR = 0xCD
VALUE_XOR = 0xAD
MAX_ENTRIES = 100_000
KEY_PATTERN = re.compile(r"#[A-Z0-9_]+\Z")
KEY_PATTERN_BYTES = re.compile(rb"#[A-Z0-9_]+\Z")

# The Western and Russian releases both store single-byte text, but in different
# code pages. Both are byte-preserving across a decode/encode round trip, so a
# misdetection can never corrupt an unedited file; it only makes the text
# unreadable while editing.
DEFAULT_ENCODING = "cp1252"
SUPPORTED_ENCODINGS = ("cp1252", "cp1251")
ENCODING_LABELS = {"cp1252": "Windows-1252 (Western)", "cp1251": "Windows-1251 (Cyrillic)"}

# Byte values each code page leaves undefined. Hitting one is proof the other
# code page is in use.
_UNDEFINED = {"cp1252": frozenset((0x81, 0x8D, 0x8F, 0x90, 0x9D)), "cp1251": frozenset((0x98,))}

# In Windows-1251 the Russian alphabet occupies 0xC0-0xFF, with 0xA8/0xB8 for
# Yo. Western text uses the high range only for isolated punctuation, so both
# the share of alphabet bytes and their run length separate the two cleanly.
_CYRILLIC_ALPHABET = frozenset(range(0xC0, 0x100)) | {0xA8, 0xB8}
_CYRILLIC_SHARE_THRESHOLD = 0.60
_CYRILLIC_RUN_THRESHOLD = 2.0


class LocdataFormatError(ValueError):
    """Raised when a binary or editable locdata document is malformed."""


@dataclass(frozen=True)
class LocdataEntry:
    key: str
    text: str


@dataclass(frozen=True)
class LocdataFile:
    entries: Tuple[LocdataEntry, ...]
    template: bytes
    source_name: str = "locdata.md"
    encoding: str = DEFAULT_ENCODING


def _xor(data: bytes, mask: int) -> bytes:
    return bytes(value ^ mask for value in data)


def normalize_encoding(value: Any, label: str = "Encoding") -> str:
    if not isinstance(value, str):
        raise LocdataFormatError("{} must be named as text.".format(label))
    normalized = value.strip().lower().replace("-", "").replace("_", "")
    aliases = {
        "cp1252": "cp1252", "windows1252": "cp1252", "1252": "cp1252", "western": "cp1252",
        "cp1251": "cp1251", "windows1251": "cp1251", "1251": "cp1251", "cyrillic": "cp1251",
        "russian": "cp1251",
    }
    if normalized not in aliases:
        raise LocdataFormatError(
            "{} must be one of {}, got {!r}.".format(label, ", ".join(SUPPORTED_ENCODINGS), value)
        )
    return aliases[normalized]


def _decode(data: bytes, label: str, encoding: str = DEFAULT_ENCODING) -> str:
    try:
        return data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise LocdataFormatError(
            "{} contains bytes that cannot be decoded as {}.".format(
                label, ENCODING_LABELS.get(encoding, encoding)
            )
        ) from exc


def _encode(text: str, label: str, encoding: str = DEFAULT_ENCODING) -> bytes:
    if not isinstance(text, str):
        raise LocdataFormatError("{} must be text.".format(label))
    if "\0" in text:
        raise LocdataFormatError("{} contains an embedded NUL character.".format(label))
    try:
        return text.encode(encoding)
    except UnicodeEncodeError as exc:
        raise LocdataFormatError(
            "{} contains a character the game cannot represent in {}.".format(
                label, ENCODING_LABELS.get(encoding, encoding)
            )
        ) from exc


def _value_blob(data: bytes) -> bytes:
    """Concatenate the value segments, skipping keys, without needing a codec."""
    segments, _starts, _count = _segments(data)
    values: List[bytes] = []
    index = 0
    while index < len(segments):
        index += 1
        if index < len(segments):
            if not KEY_PATTERN_BYTES.fullmatch(_xor(segments[index], KEY_XOR)):
                values.append(_xor(segments[index], VALUE_XOR))
                index += 1
    return b"".join(values)


def detect_encoding(data: bytes) -> str:
    """Guess the code page of a binary locdata container."""
    blob = _value_blob(data)
    present = set(blob)
    # An undefined byte in one code page is decisive evidence for the other.
    cp1252_impossible = bool(present & _UNDEFINED["cp1252"])
    cp1251_impossible = bool(present & _UNDEFINED["cp1251"])
    if cp1252_impossible and not cp1251_impossible:
        return "cp1251"
    if cp1251_impossible and not cp1252_impossible:
        return "cp1252"

    high = [byte for byte in blob if byte > 0x7F]
    if not high:
        return DEFAULT_ENCODING
    share = sum(1 for byte in high if byte in _CYRILLIC_ALPHABET) / len(high)

    runs: List[int] = []
    current = 0
    for byte in blob:
        if byte > 0x7F:
            current += 1
        elif current:
            runs.append(current)
            current = 0
    if current:
        runs.append(current)
    mean_run = sum(runs) / len(runs) if runs else 0.0

    if share >= _CYRILLIC_SHARE_THRESHOLD and mean_run >= _CYRILLIC_RUN_THRESHOLD:
        return "cp1251"
    return DEFAULT_ENCODING


def _layout(data: bytes) -> Tuple[int, int, int]:
    if len(data) < POOL_DATA_OFFSET:
        raise LocdataFormatError("The file is too small to be a Fantasy Wars locdata container.")
    first_count, entry_count, third_count = struct.unpack_from("<III", data, 0)
    if not 0 < entry_count <= MAX_ENTRIES:
        raise LocdataFormatError("Implausible localization entry count: {}.".format(entry_count))
    used = struct.unpack_from("<I", data, POOL_HEADER_OFFSET + 12)[0]
    end = POOL_DATA_OFFSET + used
    if used == 0 or end > len(data):
        raise LocdataFormatError("The localization string-pool size is invalid.")
    if data[POOL_HEADER_OFFSET:POOL_HEADER_OFFSET + 12] != b"\0" * 8 + b"\xff" * 4:
        raise LocdataFormatError("The string-pool header is not recognized.")
    return entry_count, used, end


def _segments(data: bytes) -> Tuple[List[bytes], List[int], int]:
    entry_count, used, end = _layout(data)
    pool = data[POOL_DATA_OFFSET:end]
    if not pool.endswith(b"\0"):
        raise LocdataFormatError("The localization string pool is missing its final terminator.")
    values = pool[:-1].split(b"\0")
    starts: List[int] = []
    offset = POOL_DATA_OFFSET
    for value in values:
        starts.append(offset)
        offset += len(value) + 1
    if offset != end:
        raise LocdataFormatError("The localization string pool could not be divided safely.")
    return values, starts, entry_count


def unpack_locdata(path: PathLike, encoding: Optional[str] = None) -> LocdataFile:
    source = Path(path)
    data = source.read_bytes()
    codec = detect_encoding(data) if encoding is None else normalize_encoding(encoding)
    segments, _starts, expected_count = _segments(data)
    entries: List[LocdataEntry] = []
    index = 0
    while index < len(segments):
        key_raw = _xor(segments[index], KEY_XOR)
        # Keys are ASCII by construction, so this probe stays codec-independent.
        # Decoding it would misfire on value bytes the code page leaves undefined.
        if not KEY_PATTERN_BYTES.fullmatch(key_raw):
            raise LocdataFormatError(
                "Expected a localization key at string-pool segment {}, got {!r}.".format(
                    index, key_raw[:80]
                )
            )
        key = key_raw.decode("ascii")
        index += 1
        text = ""
        if index < len(segments):
            if not KEY_PATTERN_BYTES.fullmatch(_xor(segments[index], KEY_XOR)):
                text = _decode(
                    _xor(segments[index], VALUE_XOR),
                    "Text for {!r}".format(key),
                    codec,
                )
                index += 1
        entries.append(LocdataEntry(key, text))
    if len(entries) != expected_count:
        raise LocdataFormatError(
            "Header declares {:,} entries, but {:,} were decoded.".format(
                expected_count, len(entries)
            )
        )
    if len({entry.key for entry in entries}) != len(entries):
        raise LocdataFormatError("The localization file contains duplicate keys.")
    return LocdataFile(tuple(entries), data, source.name, codec)


def write_editable(document: LocdataFile, path: PathLike) -> None:
    target = Path(path)
    template_path = target.with_suffix(".template")
    payload: Dict[str, Any] = {
        "format": FORMAT_NAME,
        "instructions": "Edit only the text values. Keep keys and their order unchanged.",
        "source_file": document.source_name,
        "source_sha256": hashlib.sha256(document.template).hexdigest(),
        "encoding": document.encoding,
        "template_file": template_path.name,
        "entries": [
            {"key": entry.key, "text": entry.text} for entry in document.entries
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_bytes(document.template)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_editable(path: PathLike) -> LocdataFile:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise LocdataFormatError("Editable text must be UTF-8.") from exc
    except json.JSONDecodeError as exc:
        raise LocdataFormatError(
            "Invalid editable text at line {}, column {}: {}.".format(
                exc.lineno, exc.colno, exc.msg
            )
        ) from exc
    if not isinstance(payload, dict) or payload.get("format") != FORMAT_NAME:
        raise LocdataFormatError("This is not a supported locdata editable document.")
    template_name = payload.get("template_file")
    if (
        not isinstance(template_name, str)
        or not template_name
        or Path(template_name).name != template_name
    ):
        raise LocdataFormatError("The editable document has an invalid template filename.")
    template_path = source.parent / template_name
    if not template_path.is_file():
        raise LocdataFormatError(
            "Companion template not found: {}. Keep the .txt and .template files together.".format(
                template_path
            )
        )
    template = template_path.read_bytes()
    declared_hash = payload.get("source_sha256")
    if declared_hash != hashlib.sha256(template).hexdigest():
        raise LocdataFormatError("The companion template checksum does not match.")
    # Files written before code-page support carry no marker and were always
    # Windows-1252, so the default keeps them repacking unchanged.
    codec = normalize_encoding(payload.get("encoding", DEFAULT_ENCODING), "Declared encoding")
    original = unpack_locdata_bytes(
        template, str(payload.get("source_file", "locdata.md")), codec
    )
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or len(raw_entries) != len(original.entries):
        raise LocdataFormatError(
            "Editable document must contain exactly {:,} entries.".format(len(original.entries))
        )
    entries: List[LocdataEntry] = []
    for index, (item, expected) in enumerate(zip(raw_entries, original.entries)):
        if not isinstance(item, dict):
            raise LocdataFormatError("Entry {} must be an object.".format(index))
        key = item.get("key")
        text = item.get("text")
        if key != expected.key:
            raise LocdataFormatError(
                "Entry {} key changed; expected {!r}.".format(index, expected.key)
            )
        if not isinstance(text, str):
            raise LocdataFormatError("Text for {!r} must be a string.".format(key))
        _encode(text, "Text for {!r}".format(key), codec)
        entries.append(LocdataEntry(key, text))
    return LocdataFile(tuple(entries), template, original.source_name, codec)


def unpack_locdata_bytes(
    data: bytes, source_name: str = "locdata.md", encoding: Optional[str] = None
) -> LocdataFile:
    codec = detect_encoding(data) if encoding is None else normalize_encoding(encoding)
    segments, _starts, expected_count = _segments(data)
    entries: List[LocdataEntry] = []
    index = 0
    while index < len(segments):
        key_raw = _xor(segments[index], KEY_XOR)
        if not KEY_PATTERN_BYTES.fullmatch(key_raw):
            raise LocdataFormatError("Invalid localization key {!r}.".format(key_raw[:80]))
        key = key_raw.decode("ascii")
        index += 1
        text = ""
        if index < len(segments):
            if not KEY_PATTERN_BYTES.fullmatch(_xor(segments[index], KEY_XOR)):
                text = _decode(_xor(segments[index], VALUE_XOR), "Text for {!r}".format(key), codec)
                index += 1
        entries.append(LocdataEntry(key, text))
    if len(entries) != expected_count:
        raise LocdataFormatError("Localization entry count does not match the header.")
    return LocdataFile(tuple(entries), data, source_name, codec)


def _boundary_map(old_segments: Sequence[bytes], new_segments: Sequence[bytes]):
    old_starts: List[int] = []
    new_starts: List[int] = []
    old_pos = POOL_DATA_OFFSET
    new_pos = POOL_DATA_OFFSET
    for old, new in zip(old_segments, new_segments):
        old_starts.append(old_pos)
        new_starts.append(new_pos)
        old_pos += len(old) + 1
        new_pos += len(new) + 1

    def translate(position: int) -> int:
        if position <= POOL_DATA_OFFSET:
            return position
        if position >= old_pos:
            return new_pos + (position - old_pos)
        low, high = 0, len(old_starts)
        while low + 1 < high:
            middle = (low + high) // 2
            if old_starts[middle] <= position:
                low = middle
            else:
                high = middle
        relative = position - old_starts[low]
        old_length = len(old_segments[low])
        new_length = len(new_segments[low])
        if relative >= old_length:
            mapped = new_length
        elif old_length == 0:
            mapped = 0
        else:
            mapped = round(relative * new_length / old_length)
        return new_starts[low] + mapped

    return translate, old_pos, new_pos


def pack_locdata(document: LocdataFile, path: PathLike) -> None:
    codec = normalize_encoding(document.encoding)
    original = unpack_locdata_bytes(document.template, document.source_name, codec)
    if len(document.entries) != len(original.entries):
        raise LocdataFormatError("The number of localization entries cannot be changed.")
    for current, expected in zip(document.entries, original.entries):
        if current.key != expected.key:
            raise LocdataFormatError("Localization keys and their order cannot be changed.")

    old_segments, _old_starts, _count = _segments(document.template)
    new_segments: List[bytes] = []
    for entry in document.entries:
        new_segments.append(_xor(_encode(entry.key, "Localization key", codec), KEY_XOR))
        if entry.text:
            new_segments.append(
                _xor(_encode(entry.text, "Text for {!r}".format(entry.key), codec), VALUE_XOR)
            )

    translate, old_end, new_end = _boundary_map(old_segments, new_segments)
    if new_end > len(document.template):
        raise LocdataFormatError(
            "Edited text exceeds the container capacity by {:,} bytes.".format(
                new_end - len(document.template)
            )
        )

    output = bytearray(document.template)
    for node_index in range(NODE_COUNT):
        node = INDEX_SIZE + node_index * NODE_SIZE
        count = struct.unpack_from("<I", output, node + 12)[0]
        if count > 7:
            raise LocdataFormatError("Invalid internal node entry count at 0x{:X}.".format(node))
        for item_index in range(count):
            field = node + 16 + item_index * 12
            pointer, length = struct.unpack_from("<II", output, field)
            range_end = pointer + length
            if POOL_DATA_OFFSET <= pointer <= old_end and range_end <= old_end:
                new_pointer = translate(pointer)
                new_range_end = translate(range_end)
                struct.pack_into("<II", output, field, new_pointer, new_range_end - new_pointer)

    pool = b"\0".join(new_segments) + b"\0"
    struct.pack_into("<I", output, POOL_HEADER_OFFSET + 12, len(pool))
    output[POOL_DATA_OFFSET:new_end] = pool
    output[new_end:] = b"\0" * (len(output) - new_end)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
