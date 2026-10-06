# CLAUDE.md

Teaching material for an MSc course in Radio Propagation: an instructor demo notebook and a
2-hour student lab on Sionna RT. Everything is written in English.

## Two repositories: never mix them

- This folder is the PUBLIC repo `giulia-open-lab/sionna-rt-course`. It contains only material
  students may see.
- `instructor/` is a separate PRIVATE repo `giulia-open-lab/sionna-rt-course-instructor`
  (solutions, course design, prompts). It has its own `.git` and is listed in `.gitignore`.
  Read its state with `git -C instructor ...`.
- Put anything that reveals solutions, model answers or the course design under `instructor/`,
  never in the public part.

## Git: commit or push only when asked

- Commit or push only when the professor explicitly asks, and only the changes they name, in
  either repository. Otherwise the professor does all Git operations.
- Other Git commands that change the repositories (add, pull, merge, rebase, reset, restore,
  checkout, stash, tag, branch) also need an explicit request. Read-only commands are always
  fine: status, diff, log, ls-files, check-ignore.
- Never add `Co-Authored-By` or any other AI attribution anywhere, including commit messages and
  suggested commit messages.
- Commit messages (including suggested ones) must never mention Claude, Claude Code or AI, not
  even the file name `CLAUDE.md`: call it "project guidelines".

## Sionna

- Pin `sionna-rt==2.2.0`. Do not rely on memory for the Sionna API: it changed in 1.0
  (PathSolver / RadioMapSolver, no TensorFlow in RT) and in 2.0 (PHY/SYS moved to PyTorch).
  Check the official documentation.

## Private context (available only when instructor/ is present)

@instructor/CLAUDE.md
