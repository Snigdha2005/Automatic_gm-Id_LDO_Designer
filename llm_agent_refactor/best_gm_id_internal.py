"""
best_gm_id_internal.py
======================
Find the best gm/Id operating point for an internally-compensated LDO.

Design methodology is identical to the original; only the implementation has
been refactored to use the PMOS / NMOS transistor classes and is now
topology-agnostic at the call site.
"""

from __future__ import annotations

import os
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from transistor import NMOS, PMOS

# ---------------------------------------------------------------------------
# Paths (override via env vars for portability)
# ---------------------------------------------------------------------------
BASE_PATH    = os.environ.get(
    "TECHPLOT_PATH",
    r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Techplots_180nm_2024",
)
ASC_FILE     = os.environ.get(
    "ASC_FILE_INTERNAL",
    r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation"
    r"\Internally_Compensated\Miller_LDO_Sim_Benches_502\LDO_loopgain_IIIT.cir",
)
LTSPICE_PATH = os.environ.get(
    "LTSPICE_PATH",
    r"C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe",
)
LOG_FILE     = ASC_FILE.replace(".cir", ".log")

MAX_GM_ID = 22


# ---------------------------------------------------------------------------
# Re-use shared utilities from the original module (kept verbatim)
# ---------------------------------------------------------------------------
from _sim_utils import (          # noqa: E402  (local import)
    modify_cir_params,
    run_ltspice_cir,
    all_in_saturation,
    analyze_loopgain,
    plot_trends,
)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def best_gm_id_internal(spec_file_name: str) -> Optional[dict]:
    """
    Sweep gm/Id values, size all transistors, run LTSpice, and return the
    parameter set that minimises the chosen figure-of-merit error while
    satisfying phase margin ≥ 45° and Cc > 0.

    Parameters
    ----------
    spec_file_name : path to the Excel spec file

    Returns
    -------
    dict of best parameters, or None if no valid point was found.
    """
    # ------------------------------------------------------------------
    # Load spec
    # ------------------------------------------------------------------
    df   = pd.read_excel(spec_file_name)
    spec = df.set_index("Spec")["Value"].to_dict()

    dropout    = round(float(spec["Vin"]) - float(spec["Vout"]), 3)
    loop_gain  = 10 ** (spec["PSRR"] / 20)
    spec["dropout"]    = dropout
    spec["loop_gain"]  = loop_gain
    spec["load_step"]  = spec["Iload|max"] - spec["Iload|min"]

    fom = int(spec["fom"])
    it  = int(spec["iterations"])

    # ------------------------------------------------------------------
    # Select Vds bias point for techplot lookup
    # ------------------------------------------------------------------
    if dropout >= 1.8:
        vds = 1.8
    elif dropout >= 0.4:
        vds = 0.4
    else:
        vds = 0.2

    # ------------------------------------------------------------------
    # Transistor objects (created once, reused across sweep)
    # ------------------------------------------------------------------
    pmos_dev = PMOS(BASE_PATH, vds)
    nmos_dev = NMOS(BASE_PATH, vds)

    # ------------------------------------------------------------------
    # gm/Id sweep
    # ------------------------------------------------------------------
    gm_id_start = 2 / vds
    gm_id_vals  = np.linspace(gm_id_start, MAX_GM_ID, int(it))

    best_gm_id   = None
    min_error    = np.inf
    best_results = None

    gm_id_trend: dict[str, list] = {k: [] for k in [
        "gm_id", "Wpass", "gm_pass", "gm_pass_light", "ro_pass",
        "Wdiff", "gm_nmos", "ro_nmos", "Wload", "gm_pmos", "ro_pmos",
        "Ldiff", "Lload", "loopgain", "fp1", "loopgain_error",
        "fp1_error", "phase_margin", "total_error", "rodiff",
        "Cc", "Iq_sim", "Power_sim",
    ]}

    for gm_id_target in gm_id_vals:

        # ==============================================================
        # 1. Pass FET (PMOS) sizing
        # ==============================================================
        pass_result = pmos_dev.size_pass_device(
            gm_id        = gm_id_target,
            Iload_mA     = float(spec["Iload|max"]),
            Iload_light_mA = float(spec["Iload|min"]),
            cload_uF     = float(spec["Cload"]),
        )
        if not pass_result:
            continue

        W         = pass_result["W"]
        gm        = pass_result["gm"]
        gm_light  = pass_result["gm_light"]
        ro        = pass_result["ro"]
        gmro      = pass_result["gmro"]
        cgs_cgd   = pass_result["cgs_cgd"]
        cgd       = pass_result["cgd"]
        wp2_light = pass_result["wp2_light"]
        gm_ro_light = pass_result["gm_ro_light"]

        # OTA gain requirement
        ota_gain        = loop_gain / gmro
        ota_gmro_needed = ota_gain * 2

        print(f"gmro required for OTA: {ota_gmro_needed:.2f}")

        # Dominant pole from pass-FET light-load analysis
        wp1 = pass_result["wp2_light"] / (loop_gain * gm_ro_light / gmro)
        fp1 = wp1 / (2 * np.pi)

        # ==============================================================
        # 2. OTA diff-pair (NMOS) sizing
        # ==============================================================
        Iq     = float(spec["Iquiescent"])
        Id     = Iq / 2          # each half-circuit branch

        nmos_result = nmos_dev.size(
            gm_id         = gm_id_target,
            Id_uA         = Id,
            gmro_required = ota_gmro_needed,
        )
        if not nmos_result:
            continue

        W_nmos    = nmos_result["W"]
        gm_nmos   = nmos_result["gm"]
        ro_nmos   = nmos_result["ro"]
        chosen_L  = nmos_result["chosen_L"]

        # ==============================================================
        # 3. OTA PMOS load sizing
        # ==============================================================
        pmos_load_result = pmos_dev.size(
            gm_id         = gm_id_target,
            Id_uA         = Iq / 2,
            gmro_required = ota_gmro_needed,
        )
        if not pmos_load_result:
            continue

        W_pmos       = pmos_load_result["W"]
        gm_pmos      = pmos_load_result["gm"]
        ro_pmos      = pmos_load_result["ro"]
        chosen_L_pmos = pmos_load_result["chosen_L"]

        # ==============================================================
        # 4. Compensation capacitor calculation
        # ==============================================================
        rodiff = (ro_pmos * ro_nmos) / (ro_pmos + ro_nmos)
        cc_cgd = 1e6 / (wp1 * rodiff * gmro)
        Cc     = cc_cgd - cgd

        # ==============================================================
        # 5. LTSpice simulation
        # ==============================================================
        params = {
            "ibias": f"{Iq}u",
            "Iload": f"{spec['Iload|min']}m",
            "Wdiff": f"{W_nmos}u",
            "Wpass": f"{W}u",
            "Cload": f"{spec['Cload']}u",
            "Cc":    f"{Cc}u",
            "Wload": f"{W_pmos}u",
            "Vin":   spec["Vin"],
            "Vout":  spec["Vout"],
            "l1":    f"{chosen_L}u",
            "l2":    f"{chosen_L_pmos}u",
        }

        raw_file = ASC_FILE.replace(".cir", ".raw")
        if os.path.exists(raw_file):
            os.remove(raw_file)

        modify_cir_params(ASC_FILE, params)
        raw_file = run_ltspice_cir(LTSPICE_PATH, ASC_FILE)

        sat_check = all_in_saturation(LOG_FILE)
        if not sat_check["all_in_saturation"]:
            print(f"  Devices not in saturation – skipping gm/Id={gm_id_target:.3f}")
            continue

        # ==============================================================
        # 6. Analyse loop-gain results
        # ==============================================================
        (loop_gain_error, fp1_error, fp1_sim,
         f0db_sim, phase_margin_sim, loopgain, fp1_val) = analyze_loopgain(
            raw_file, fp1, spec["PSRR"]
        )

        total_error = loop_gain_error if fom == 1 else fp1_error

        # ==============================================================
        # 7. Accumulate trend data
        # ==============================================================
        gm_id_trend["gm_id"].append(gm_id_target)
        gm_id_trend["Wpass"].append(W)
        gm_id_trend["gm_pass"].append(gm)
        gm_id_trend["gm_pass_light"].append(gm_light)
        gm_id_trend["ro_pass"].append(ro)
        gm_id_trend["Wdiff"].append(W_nmos)
        gm_id_trend["gm_nmos"].append(gm_nmos)
        gm_id_trend["ro_nmos"].append(ro_nmos)
        gm_id_trend["Wload"].append(W_pmos)
        gm_id_trend["gm_pmos"].append(gm_pmos)
        gm_id_trend["ro_pmos"].append(ro_pmos)
        gm_id_trend["Ldiff"].append(chosen_L)
        gm_id_trend["Lload"].append(chosen_L_pmos)
        gm_id_trend["loopgain"].append(loopgain)
        gm_id_trend["fp1"].append(fp1_val)
        gm_id_trend["loopgain_error"].append(loop_gain_error)
        gm_id_trend["fp1_error"].append(fp1_error)
        gm_id_trend["phase_margin"].append(phase_margin_sim)
        gm_id_trend["total_error"].append(total_error)
        gm_id_trend["Cc"].append(Cc)
        gm_id_trend["rodiff"].append(rodiff)
        gm_id_trend["Iq_sim"].append(sat_check["m2_id_uA"])
        gm_id_trend["Power_sim"].append(sat_check["m2_id_uA"] * spec["Vin"])

        # ==============================================================
        # 8. Track best solution
        # ==============================================================
        if (total_error < min_error and total_error > 0
                and phase_margin_sim >= 45 and Cc > 0):
            min_error  = total_error
            best_gm_id = gm_id_target
            best_results = {
                "Wpass":          W,
                "Wdiff":          W_nmos,
                "Wload":          W_pmos,
                "gm_id":          gm_id_target,
                "fp1_sim":        fp1_sim,
                "phase_margin":   phase_margin_sim,
                "loop_gain_error": loop_gain_error,
                "fp1_error":      fp1_error,
                "l1":             chosen_L,
                "l2":             chosen_L_pmos,
                "Cc":             Cc,
                "Cload":          spec["Cload"],
                "Iq_sim":         sat_check["m2_id_uA"],
                "Iq_error":       (spec["Iquiescent"] / 2
                                   - sat_check["m2_id_uA"]) * 100
                                  / spec["Iquiescent"],
                "Power":          sat_check["m2_id_uA"] * spec["Vin"],
            }

    # ------------------------------------------------------------------
    # Save trend plots
    # ------------------------------------------------------------------
    plot_trends(gm_id_trend, spec_file_name)

    return best_results
