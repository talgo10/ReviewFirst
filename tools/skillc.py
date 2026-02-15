#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

SECTION_PATTERN = re.compile(r"^(public|private|tests):\s*$")
DOC_HEADER_KEYS = {
    "intent",
    "inputs",
    "errors",
    "effects",
    "requires",
    "ensures",
}


@dataclass
class SkillProgram:
    source_path: Path
    skill_name: str
    lines_to_print: list[str]


def fail(message: str) -> None:
    raise SystemExit(f"skillc error: {message}")


def split_sections(content: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    ordered_sections: list[str] = []

    for raw_line in content.splitlines():
        section_match = SECTION_PATTERN.match(raw_line.strip())
        if section_match:
            current = section_match.group(1)
            ordered_sections.append(current)
            sections[current] = []
            continue

        if current is None:
            if raw_line.strip():
                fail("declarations outside of public/private/tests sections")
            continue

        sections[current].append(raw_line)

    if ordered_sections[:2] != ["public", "private"]:
        fail("top-level sections must begin with public: then private:")
    if len(ordered_sections) != len(set(ordered_sections)):
        fail("duplicate top-level sections are not allowed")

    return sections


def extract_program(source_path: Path) -> SkillProgram:
    text = source_path.read_text(encoding="utf-8")
    sections = split_sections(text)

    public_lines = sections.get("public", [])

    doc_headers: set[str] = set()
    skill_line_idx = -1
    skill_name = ""
    for idx, line in enumerate(public_lines):
        stripped = line.strip()
        if stripped.startswith("///"):
            cleaned = stripped.removeprefix("///").strip()
            if ":" in cleaned:
                key = cleaned.split(":", 1)[0].strip()
                if key in DOC_HEADER_KEYS:
                    doc_headers.add(key)
            continue

        if stripped.startswith("pub skill"):
            skill_line_idx = idx
            name_match = re.search(r"pub skill\s+([A-Z][A-Za-z0-9]*)", stripped)
            if not name_match:
                fail("exported skill name must be PascalCase")
            skill_name = name_match.group(1)
            break

    if skill_line_idx < 0:
        fail("public section must include a pub skill")

    missing_headers = DOC_HEADER_KEYS - doc_headers
    if missing_headers:
        fail(f"missing required doc headers: {', '.join(sorted(missing_headers))}")

    steps_start = -1
    for idx in range(skill_line_idx + 1, len(public_lines)):
        if public_lines[idx].strip() == "steps:":
            steps_start = idx + 1
            break

    if steps_start < 0:
        fail("pub skill must include a steps: block")

    print_lines: list[str] = []
    for idx in range(steps_start, len(public_lines)):
        stmt = public_lines[idx].strip()
        if not stmt:
            continue
        if stmt.startswith("do console.println"):
            msg_match = re.search(r"\((.*)\)\s*$", stmt)
            if not msg_match:
                fail("invalid do console.println syntax")
            raw_value = msg_match.group(1).strip()
            if not (raw_value.startswith('"') and raw_value.endswith('"')):
                fail("console.println only supports string literals in POC")
            print_lines.append(raw_value[1:-1])
        elif stmt.startswith("return"):
            break
        else:
            fail(f"unsupported statement in steps block: {stmt}")

    if not print_lines:
        fail("steps block must include at least one do console.println statement")

    return SkillProgram(source_path=source_path, skill_name=skill_name, lines_to_print=print_lines)


def generate_c(program: SkillProgram, out_c: Path) -> None:
    escaped_lines = [line.replace('\\', '\\\\').replace('"', '\\"') for line in program.lines_to_print]
    print_calls = "\n".join([f'    puts("{line}");' for line in escaped_lines])
    c_src = f"""#include <stdio.h>

int main(void) {{
{print_calls}
    return 0;
}}
"""
    out_c.write_text(c_src, encoding="utf-8")


def compile_binary(c_file: Path, output_binary: Path) -> None:
    compiler = shutil.which("gcc") or shutil.which("cc")
    if compiler is None:
        fail("gcc/cc compiler not found on PATH")

    cmd = [compiler, str(c_file), "-O2", "-o", str(output_binary)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"native compile failed: {result.stderr.strip()}")


def build_manifest(program: SkillProgram, output_binary: Path, mode: str) -> dict[str, object]:
    source_text = program.source_path.read_bytes()
    binary_text = output_binary.read_bytes()
    return {
        "compiler": "skillc-poc-0.1",
        "build_mode": mode,
        "source": {
            "path": str(program.source_path),
            "sha256": hashlib.sha256(source_text).hexdigest(),
        },
        "artifact": {
            "path": str(output_binary),
            "sha256": hashlib.sha256(binary_text).hexdigest(),
        },
    }


def cmd_build(entry: str, output: str, mode: str) -> None:
    source_path = Path(entry)
    if not source_path.exists():
        fail(f"entry file does not exist: {entry}")

    output_binary = Path(output)
    output_binary.parent.mkdir(parents=True, exist_ok=True)

    program = extract_program(source_path)
    c_file = output_binary.with_suffix(".c")
    generate_c(program, c_file)
    compile_binary(c_file, output_binary)

    manifest = build_manifest(program, output_binary, mode)
    manifest_path = output_binary.with_suffix(output_binary.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Built {program.skill_name} -> {output_binary}")
    print(f"Manifest: {manifest_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skillc", description="ReviewFirst SkillScript POC compiler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="build an entry file to a native executable")
    build_parser.add_argument("entry", help="entry .skill file")
    build_parser.add_argument("-o", "--output", required=True, help="output executable path")
    build_parser.add_argument("--mode", default="debug", choices=["debug", "release"])

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args.entry, args.output, args.mode)
        return

    fail(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
