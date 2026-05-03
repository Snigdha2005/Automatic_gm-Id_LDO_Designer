"""
_sim_utils.py
=============
Shared simulation utilities: LTSpice runner, .cir parameter modifier,
saturation checker, loop-gain analyser, and trend plotter.

These functions are identical in logic to the originals – only extracted into
a single shared module so they can be imported by both
best_gm_id_internal.py and best_gm_id_external.py without duplication.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional, Tuple

import ltspice
import matplotlib.pyplot as plt
import numpy as np


# ---------------------------------------------------------------------------
# .cir parameter modifier
# ---------------------------------------------------------------------------

def modify_cir_params(cir_file_path: str, param_dict: dict,
                      param_line_identifier: str = ".param") -> str:
    """
    Update the .param line in a SPICE .cir file with values from *param_dict*.

    Only keys that already exist in the .param line are modified; unknown
    keys are silently ignored.  Returns the file path.
    """
    with open(cir_file_path, "r") as fh:
        lines = fh.readlines()

    for i, line in enumerate(lines):
        if line.strip().startswith(param_line_identifier):
            parts = line.strip().split()[1:]
            for j, part in enumerate(parts):
                key, _ = part.split("=")
                if key in param_dict:
                    parts[j] = f"{key}={param_dict[key]}"
            lines[i] = param_line_identifier + " " + " ".join(parts) + "\n"

    with open(cir_file_path, "w") as fh:
        fh.writelines(lines)

    return cir_file_path


# ---------------------------------------------------------------------------
# LTSpice batch runner
# ---------------------------------------------------------------------------

def run_ltspice_cir(ltspice_exe: str, cir_file_path: str) -> str:
    """
    Run LTSpice in batch mode on *cir_file_path*.

    Returns the path to the produced .raw file.
    Raises FileNotFoundError if the .raw file is not created.
    """
    cmd = [ltspice_exe, "-b", cir_file_path]
    subprocess.run(cmd, check=True)

    raw_file = cir_file_path.replace(".cir", ".raw")
    if not os.path.exists(raw_file):
        raise FileNotFoundError(
            f"LTSpice did not produce a raw file: {raw_file}"
        )
    return raw_file


# ---------------------------------------------------------------------------
# Saturation checker
# ---------------------------------------------------------------------------

def all_in_saturation(op_file: str) -> dict:
    """
    Parse the LTSpice .log operating-point table and check that every device
    satisfies |Vds| > |Vgs − Vth| (saturation condition).

    Returns
    -------
    dict with keys:
        all_in_saturation : bool
        m2_id_A           : float | None  – drain current of M2 in Amps
        m2_id_uA          : float | None  – drain current of M2 in µA
    """
    numeric_rows = {"Id", "Vgs", "Vds", "Vth"}
    op_values: dict[str, dict] = {}

    with open(op_file, "r") as fh:
        lines = fh.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("Name:"):
            devices = line.split()[1:]
            for dev in devices:
                op_values.setdefault(dev, {})

            i += 1
            while i < len(lines):
                row_line = lines[i].strip()
                if not row_line or row_line.startswith("Name:"):
                    break
                parts    = row_line.split()
                row_name = parts[0].strip(":")
                values   = parts[1:]
                if len(values) != len(devices):
                    i += 1
                    continue
                if row_name in numeric_rows:
                    for dev, val in zip(devices, values):
                        try:
                            op_values[dev][row_name] = float(
                                val.replace("D", "e")
                            )
                        except ValueError:
                            op_values[dev][row_name] = None
                i += 1
            continue
        i += 1

    all_sat = True
    for dev, vals in op_values.items():
        try:
            vgs = vals["Vgs"]
            vds = vals["Vds"]
            vth = vals["Vth"]
            if not (abs(vds) > abs(vgs - vth)):
                all_sat = False
        except KeyError:
            all_sat = False

    Id = op_values.get("m2", {}).get("Id", None)

    return {
        "all_in_saturation": all_sat,
        "m2_id_A":           Id,
        "m2_id_uA":          (Id * 1e6) if Id is not None else None,
    }


# ---------------------------------------------------------------------------
# Loop-gain analyser
# ---------------------------------------------------------------------------

def analyze_loopgain(
    raw_file: str,
    fp1_theo: float,
    loop_gain_theo_db: float,
) -> Tuple[float, float, float, float, float, float, float]:
    """
    Extract loop-gain metrics from an LTSpice .raw file.

    Parameters
    ----------
    raw_file         : path to the .raw simulation output
    fp1_theo         : theoretical dominant pole [Hz]
    loop_gain_theo_db: theoretical loop gain [dB]

    Returns
    -------
    (loop_gain_error, fp1_error, fp1_sim, f0db_sim,
     phase_margin_sim, low_mag_db, fp1_val)
    """
    l = ltspice.Ltspice(raw_file)
    l.parse()

    freq   = l.get_frequency()
    vout   = l.get_data("V(out)")
    mag_db = 20 * np.log10(np.abs(vout))
    phase_deg = np.angle(vout, deg=True)

    low_mag_db = mag_db[0]

    # -3 dB pole
    minus3_db = low_mag_db - 3
    fp1_idx   = np.argmin(np.abs(mag_db - minus3_db))
    fp1_sim   = freq[fp1_idx]
    fp1_val   = fp1_sim

    # 0 dB crossover → phase margin
    zero_db_idx      = np.argmin(np.abs(mag_db - 0))
    f0db_sim         = freq[zero_db_idx]
    phase_margin_sim = phase_deg[zero_db_idx]

    loop_gain_error = (low_mag_db - loop_gain_theo_db) / loop_gain_theo_db * 100
    fp1_error       = (fp1_theo - fp1_sim) / fp1_theo * 100

    return (loop_gain_error, fp1_error, fp1_sim,
            f0db_sim, phase_margin_sim, low_mag_db, fp1_val)


# ---------------------------------------------------------------------------
# Trend plotter
# ---------------------------------------------------------------------------

def plot_trends(gm_id_trend: dict, spec_file_name: str) -> None:
    """
    Save per-parameter trend plots (vs gm/Id) to a sub-folder named after
    the spec file.
    """
    base    = os.path.basename(spec_file_name)
    folder  = os.path.splitext(base)[0]
    out_dir = os.path.join(os.path.dirname(spec_file_name), folder)
    os.makedirs(out_dir, exist_ok=True)

    gm = gm_id_trend["gm_id"]

    def save_plot(y_key: str, ylabel: str, title: str, filename: str) -> None:
        plt.figure()
        plt.plot(gm, gm_id_trend[y_key], marker="o")
        plt.xlabel("gm/Id")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.grid(True)
        plt.locator_params(axis="x", nbins=20)
        plt.locator_params(axis="y", nbins=20)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, filename), dpi=300)
        plt.close()

    _plots = [
        ("Wpass",          "Wpass (µm)",         "Pass Device Width vs gm/Id",       "Wpass.png"),
        ("Wdiff",          "Wdiff (µm)",          "Diff Pair Width vs gm/Id",         "Wdiff.png"),
        ("Wload",          "Wload (µm)",          "PMOS Load Width vs gm/Id",         "Wload.png"),
        ("gm_pass",        "gm_pass (S)",         "Pass Device gm vs gm/Id",          "gm_pass.png"),
        ("gm_nmos",        "gm_nmos (S)",         "Diff Pair gm vs gm/Id",            "gm_nmos.png"),
        ("gm_pmos",        "gm_pmos (S)",         "PMOS Load gm vs gm/Id",            "gm_pmos.png"),
        ("gm_pass_light",  "gm_pass_light (S)",   "Pass Device gm_light vs gm/Id",    "gm_pass_light.png"),
        ("ro_pass",        "ro_pass (Ω)",          "Pass Device ro vs gm/Id",          "ro_pass.png"),
        ("ro_nmos",        "ro_nmos (Ω)",          "Diff Pair ro vs gm/Id",            "ro_nmos.png"),
        ("ro_pmos",        "ro_pmos (Ω)",          "PMOS Load ro vs gm/Id",            "ro_pmos.png"),
        ("Ldiff",          "Ldiff (µm)",           "Chosen NMOS Length vs gm/Id",      "Ldiff.png"),
        ("Lload",          "Lload (µm)",           "Chosen PMOS Length vs gm/Id",      "Lload.png"),
        ("loopgain",       "Loop Gain (dB)",       "Loop Gain vs gm/Id",               "loopgain.png"),
        ("fp1",            "fp1 (Hz)",             "Simulated fp1 vs gm/Id",           "fp1_sim.png"),
        ("Cc",             "Cc (µF)",              "Cc vs gm/Id",                      "Cc.png"),
        ("rodiff",         "Rodiff (Ω)",            "Theoretical Rodiff vs gm/Id",      "rodiff.png"),
        ("Iq_sim",         "Iq_sim (µA)",          "Simulated Iq vs gm/Id",            "Iq_sim.png"),
        ("Power_sim",      "Power_sim (µW)",       "Simulated Power vs gm/Id",         "Power_sim.png"),
        ("loopgain_error", "Loop Gain Error (%)",  "Loop Gain Error vs gm/Id",         "loopgain_error.png"),
        ("fp1_error",      "fp1 Error (%)",        "fp1 Error vs gm/Id",               "fp1_error.png"),
        ("phase_margin",   "Phase Margin (deg)",   "Phase Margin vs gm/Id",            "phase_margin.png"),
        ("total_error",    "Total Error (%)",      "Total Error vs gm/Id",             "total_error.png"),
    ]

    for (y_key, ylabel, title, filename) in _plots:
        if y_key in gm_id_trend and gm_id_trend[y_key]:
            save_plot(y_key, ylabel, title, filename)
