#!/usr/bin/env python3
"""Generate the student version of the lab from the instructor's solutions notebook.

Usage, from the root of the public repository:

    python tools/make_student_version.py [SOURCE] [TARGET]

SOURCE defaults to instructor/02_lab_solutions.ipynb (private repository, cloned in
instructor/) and TARGET to notebooks/02_lab_student.ipynb.

Markers used in the solutions notebook (compatible with nbgrader, which only looks for
"BEGIN SOLUTION" and "END SOLUTION" in a line):

* code cells: a block from a line "### BEGIN SOLUTION [Ex N.M] <what to do>" to a line
  "### END SOLUTION" becomes, with the same indentation,
      # TODO [Ex N.M]: <what to do>
      raise NotImplementedError("Ex N.M not completed yet: <what to do>")
* markdown cells: a block from "<!-- BEGIN SOLUTION [label] -->" to "<!-- END SOLUTION -->"
  becomes "**Your answer:** _write here_";
* a markdown cell whose first line is "<!-- INSTRUCTOR ONLY -->" is removed.

All outputs and execution counts are removed and an "Open in Colab" badge is added at the top.
Only the Python standard library is used.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO / "instructor" / "02_lab_solutions.ipynb"
DEFAULT_TARGET = REPO / "notebooks" / "02_lab_student.ipynb"

COLAB_BADGE = ("[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]"
               "(https://colab.research.google.com/github/giulia-open-lab/sionna-rt-course/"
               "blob/main/notebooks/02_lab_student.ipynb)")

# Marker definitions
CODE_BEGIN = re.compile(r"^(?P<indent>[ \t]*)### BEGIN SOLUTION \[(?P<label>Ex \d+(?:\.\d+)?)\] "
                        r"(?P<todo>\S.*?)\s*$")
CODE_END = re.compile(r"^[ \t]*### END SOLUTION\s*$")
MD_BEGIN = re.compile(r"^<!-- BEGIN SOLUTION \[[^\]]+\] -->$")
MD_END = "<!-- END SOLUTION -->"
INSTRUCTOR_ONLY = "<!-- INSTRUCTOR ONLY -->"
ANSWER_PLACEHOLDER = "**Your answer:** _write here_"
FORBIDDEN = ("BEGIN SOLUTION", "END SOLUTION", INSTRUCTOR_ONLY)


def cell_source(cell):
    source = cell["source"]
    return "".join(source) if isinstance(source, list) else source


def convert_code(source, where):
    """Replace every solution block of a code cell with a TODO and a NotImplementedError."""
    out, block, gaps = [], None, []
    for line in source.split("\n"):
        if block is None:
            match = CODE_BEGIN.match(line)
            if match:
                block = match
            elif "BEGIN SOLUTION" in line or "END SOLUTION" in line:
                raise ValueError(f"{where}: malformed or unbalanced marker: {line.strip()!r}")
            else:
                out.append(line)
        elif CODE_END.match(line):
            indent, label, todo = block["indent"], block["label"], block["todo"]
            out.append(f"{indent}# TODO [{label}]: {todo}")
            out.append(f"{indent}raise NotImplementedError({json.dumps(f'{label} not completed yet: {todo}')})")
            gaps.append(label)
            block = None
        elif "BEGIN SOLUTION" in line:
            raise ValueError(f"{where}: nested solution block: {line.strip()!r}")
    if block is not None:
        raise ValueError(f"{where}: missing '### END SOLUTION' for [{block['label']}]")
    return "\n".join(out), gaps


def convert_markdown(source, where):
    """Replace every model answer of a markdown cell with the answer placeholder."""
    out, inside, answers = [], False, 0
    for line in source.split("\n"):
        stripped = line.strip()
        if not inside:
            if MD_BEGIN.match(stripped):
                inside = True
                out.append(ANSWER_PLACEHOLDER)
                answers += 1
            elif "BEGIN SOLUTION" in stripped or stripped == MD_END:
                raise ValueError(f"{where}: malformed or unbalanced marker: {stripped!r}")
            else:
                out.append(line)
        elif stripped == MD_END:
            inside = False
        elif "BEGIN SOLUTION" in stripped:
            raise ValueError(f"{where}: nested solution block: {stripped!r}")
    if inside:
        raise ValueError(f"{where}: missing '{MD_END}'")
    return "\n".join(out), answers


def to_lines(text):
    return text.splitlines(keepends=True)


def make_student_notebook(nb):
    cells, gaps, answers, removed = [], [], 0, 0
    for index, cell in enumerate(nb["cells"]):
        source, where = cell_source(cell), f"cell {index}"
        new = {"cell_type": cell["cell_type"], "metadata": {}}
        if "id" in cell:
            new["id"] = cell["id"]
        if cell["cell_type"] == "markdown":
            if source.lstrip().startswith(INSTRUCTOR_ONLY):
                removed += 1
                continue
            text, n = convert_markdown(source, where)
            answers += n
        elif cell["cell_type"] == "code":
            text, cell_gaps = convert_code(source, where)
            gaps += cell_gaps
            new["execution_count"] = None
            new["outputs"] = []
        else:
            text = source
        new["source"] = to_lines(text)
        cells.append(new)

    if cells and cells[0]["cell_type"] == "markdown":
        cells[0]["source"] = to_lines(COLAB_BADGE + "\n\n" + "".join(cells[0]["source"]))
    else:
        cells.insert(0, {"cell_type": "markdown", "metadata": {}, "source": to_lines(COLAB_BADGE)})

    student = {"cells": cells,
               "metadata": {"kernelspec": nb["metadata"].get("kernelspec", {}),
                            "language_info": {"name": "python"}},
               "nbformat": nb.get("nbformat", 4),
               "nbformat_minor": nb.get("nbformat_minor", 5)}
    text = json.dumps(student)
    for marker in FORBIDDEN:
        if marker in text:
            raise ValueError(f"the student notebook would still contain {marker!r}")
    return student, gaps, answers, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("target", nargs="?", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    if not args.source.exists():
        sys.exit(f"Source notebook not found: {args.source} (is the instructor repository cloned in instructor/?)")
    nb = json.loads(args.source.read_text(encoding="utf-8"))
    student, gaps, answers, removed = make_student_notebook(nb)
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(json.dumps(student, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.target}: {len(student['cells'])} cells, {len(gaps)} code gaps "
          f"({', '.join(sorted(set(gaps), key=lambda s: [int(x) for x in s[3:].split('.')]))}), "
          f"{answers} answer cells, {removed} instructor-only cells removed, outputs stripped.")


if __name__ == "__main__":
    main()
