# CLAUDE.md

Teaching material for an MSc course in Radio Propagation: an instructor demo notebook and a
2-hour student lab on Sionna RT. Everything is written in English.

## Two repositories: never mix them

- This folder is the PUBLIC repo `giulia-open-lab/sionna-rt-course`. It contains only material
  students may see.
- `instructor/` is a separate PRIVATE repo `giulia-open-lab/sionna-rt-course-instructor`
  (solutions, course design, prompts). It has its own `.git` and is listed in `.gitignore`.
  Run git there with `git -C instructor ...`.
- Before every commit in the public repo, check `git diff --cached --name-only`: no solutions,
  no model answers, no course design, nothing from `instructor/`.

## Sionna

- Pin `sionna-rt==2.2.0`. Do not rely on memory for the Sionna API: it changed in 1.0
  (PathSolver / RadioMapSolver, no TensorFlow in RT) and in 2.0 (PHY/SYS moved to PyTorch).
  Check the official documentation.

## Private context (available only when instructor/ is present)

@instructor/CLAUDE.md
