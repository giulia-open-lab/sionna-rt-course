# Sionna RT for Radio Propagation

Open teaching material on ray tracing for radio propagation with
[Sionna RT](https://nvlabs.github.io/sionna/rt/), developed for the MSc course *Radio
Propagation*. It explains what a ray tracer for radio propagation is, validates it against the
theory students know (Friis, the two-ray model with Fresnel coefficients), and uses it to study
multipath, delay spread, coherence bandwidth and coverage.

## Contents

| Notebook | Description | Open |
|---|---|---|
| [`notebooks/01_instructor_demo.ipynb`](notebooks/01_instructor_demo.ipynb) | Lecture demo (about 60 min, run live by the instructor; saved with outputs) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/giulia-open-lab/sionna-rt-course/blob/main/notebooks/01_instructor_demo.ipynb) |
| [`notebooks/02_lab_student.ipynb`](notebooks/02_lab_student.ipynb) | Hands-on lab (2 hours, alone or in pairs, after the lecture) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/giulia-open-lab/sionna-rt-course/blob/main/notebooks/02_lab_student.ipynb) |

The notebooks use `sionna-rt` 2.2.0 (with Mitsuba 3.9.1 and Dr.Jit 1.5.0). They run on a GPU or,
more slowly, on a CPU. They use only the scenes that ship with Sionna RT or that are built in the
code, so no extra download is needed.

## Running on Google Colab

1. Click the **Open in Colab** badge of the notebook.
2. Optional: *Runtime → Change runtime type → T4 GPU*. Without a GPU the notebooks run on the CPU.
3. Run the first code cell (setup). On a fresh runtime it installs `sionna-rt==2.2.0` (about
   280 MB) and **restarts the runtime**, as the official Sionna tutorials do. This is expected:
   when Colab says the session has restarted, **run the setup cell again**.
4. The setup cell prints the versions and the Mitsuba variant: `cuda_ad_mono_polarized` (GPU) or
   `llvm_ad_mono_polarized` (CPU). Then run the cells in order.

To keep your work on Colab, save a copy in your Drive (*File → Save a copy in Drive*) or download
the `.ipynb` file (*File → Download → Download .ipynb*).

## Running on your own computer or on the lab computers

You need Python 3.11, 3.12 or 3.13 (the pinned NumPy and matplotlib versions have no wheels for
Python 3.14) and, on a computer without an NVIDIA GPU, the LLVM library (see below).

```bash
git clone https://github.com/giulia-open-lab/sionna-rt-course.git
cd sionna-rt-course
python3 -m venv ~/venvs/sionna-rt-course              # or a conda environment
source ~/venvs/sionna-rt-course/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name sionna-rt-course --display-name "Python (sionna-rt-course)"
```

Then open the notebook in Jupyter (or VS Code) and select the kernel **Python
(sionna-rt-course)**. If Jupyter is not installed on the computer, also run
`pip install jupyterlab` in the environment and start it with `jupyter lab`.

### Note for the lab administrators: LLVM for the CPU

Without an NVIDIA GPU, Sionna RT runs on the CPU through Dr.Jit's LLVM backend, which needs the
LLVM shared library (`libLLVM`). It cannot be installed with pip:

- **Ubuntu/Debian:** `sudo apt install libllvm18` (or another `libllvmNN` package available in the
  distribution). Dr.Jit finds `/usr/lib/x86_64-linux-gnu/libLLVM*.so.*` automatically. The
  material was tested with LLVM 20.1, the version installed on Colab.
- **Elsewhere:** set the environment variable `DRJIT_LIBLLVM_PATH` to the full path of the LLVM
  shared library.

If the library is missing, the setup cell stops with the message *"No GPU was found and the LLVM
library needed by the CPU variant is missing"*.

## Execution times

Measured with a clean kernel and an empty Dr.Jit kernel cache (the first call of each solver
includes the compilation of its kernels):

| Notebook | GPU (NVIDIA RTX A6000) | CPU, 2 threads (as on Colab without GPU) |
|---|---|---|
| Lecture demo, whole notebook | about 1 min | about 5 min (slowest cell about 50 s) |
| Lab, all exercises completed | about 25 s | about 1.5 min (slowest cell about 20 s) |

These measurements were made on a workstation. Colab itself (T4 GPU or 2 vCPUs) was not measured
and is slower than this workstation, so expect longer times there (see the manual Colab checklist
below).

## Troubleshooting

- **"sionna-rt is not installed"** (outside Colab): activate the environment and run
  `pip install -r requirements.txt`.
- **The Colab session restarts after the setup cell:** expected on the first run; run the setup
  cell again.
- **No GPU:** nothing to do; the CPU variant is selected automatically. To force the CPU on a
  machine with a GPU, set `FORCE_CPU = True` in the setup cell and restart the kernel.
- **LLVM error on a CPU-only machine:** see *Note for the lab administrators* above.
- **Numbers slightly different from a classmate's or from the saved outputs:** ray tracing with
  a finite number of rays is not bit-for-bit reproducible. The GPU and CPU variants can also find
  slightly different sets of weak diffracted paths (up to a few tenths of a dB in some cases). The
  automatic checks of the lab use tolerances that cover this.
- **A cell in the lab stops with `NotImplementedError: Ex N.M not completed yet`:** that part is
  still a `TODO`: complete it and run the cell again.

## Manual Colab checklist (for instructors)

These steps could not be run automatically and should be done once on Colab before the lecture:

1. Open both notebooks with the badges, once with a **T4 GPU** runtime and once with a **CPU**
   runtime.
2. Run the setup cell: it should install `sionna-rt==2.2.0`, restart the runtime, and after a
   second run print the variant (`cuda_ad_mono_polarized` on T4, `llvm_ad_mono_polarized` on CPU)
   with no LLVM error.
3. Demo: *Runtime → Run all*. Expect no error, and note the slowest cells: they should take less
   than 60 s on the T4 and less than 3 min on the CPU.
4. Lab (student version): *Runtime → Run all*. Only the `TODO` cells should stop, with
   `NotImplementedError: Ex N.M not completed yet`, and the check cells should print
   *"Exercise N.M not completed yet"*.

## Repository structure

```
README.md, LICENSE, requirements.txt
notebooks/01_instructor_demo.ipynb   lecture demo, with outputs
notebooks/02_lab_student.ipynb       lab, student version (no outputs), generated by the script
tools/make_student_version.py        generates the student version from the solutions notebook
```

The student notebook is generated by `tools/make_student_version.py` from a solutions notebook
kept in the instructors' private repository: do not edit it by hand.

## References

- Sionna RT documentation: https://nvlabs.github.io/sionna/rt/index.html
- F. Aït Aoudia et al., "Sionna RT: Technical Report", arXiv:2504.21719, 2025.
- ITU-R P.2040-4 (09/2025), "Effects of building materials and structures on radiowave
  propagation in the range of 1 MHz to 450 GHz".
- 3GPP TR 38.901 V19.5.0, "Study on channel model for frequencies from 0.5 to 100 GHz".

## License

The course material is released under the [MIT License](LICENSE). Sionna RT, Mitsuba and Dr.Jit
are third-party software with their own licenses (Sionna RT: Apache-2.0).
