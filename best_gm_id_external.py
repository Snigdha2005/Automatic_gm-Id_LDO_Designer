import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
import os
import subprocess
import ltspice
import matplotlib.pyplot as plt
import re

# -----------------------------
# Constants & Paths
# -----------------------------
MAX_GM_ID = 22
L_COL = "L___180nm"   # Only use length = 0.18 µm
BASE_PATH = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Techplots_180nm_2024"
ASC_FILE = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_loopgain_IIIT.cir"
PSRR_ASC_FILE = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_PSRR_IIIT.cir"
LTSPICE_PATH = r"C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe"
LOG_FILE = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_loopgain_IIIT.log"

# ##print("1: FOM = Gain(dB) Error")
# ##print("2: FOM = Unity Gain Bandwidth Error")
# fom = int(input())
# ##print("Number of iterations: ")
# it = int(input())
# -----------------------------
# Utility Functions
# -----------------------------
def build_filename(device, vds, n_or_p, W=5000):
    vds_str = str(vds).replace('.', 'p')
    filename = f"{device}_{n_or_p}GMID_VDS_{vds_str}V_W_{W}um.csv"
    return os.path.join(BASE_PATH, filename)
def modify_cir_params(cir_file_path, param_dict, param_line_identifier=".param"):
    """
    Updates the .param line in a .cir SPICE file with new values.
    """
    with open(cir_file_path, 'r') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line.strip().startswith(param_line_identifier):
            parts = line.strip().split()[1:]
            for j, part in enumerate(parts):
                key, _ = part.split("=")
                if key in param_dict:
                    parts[j] = f"{key}={param_dict[key]}"
            lines[i] = param_line_identifier + " " + " ".join(parts) + "\n"
    
    with open(cir_file_path, 'w') as f:
        f.writelines(lines)
    
    # ##print(f"Updated parameters in {cir_file_path}")
    return cir_file_path
def plot_trends(gm_id_trend, spec_file_name):

    # -----------------------------
    # Create directory based on spec file name
    # -----------------------------
    # spec_file_name = spec_file_name.split("/")
    # ##print(spec_file_name)
    base = os.path.basename(spec_file_name)        # spec1.xlsx
    folder = os.path.splitext(base)[0]             # spec1
    out_dir = os.path.join(os.path.dirname(spec_file_name), folder)

    os.makedirs(out_dir, exist_ok=True)
    ##print(f"[INFO] Saving trend plots to: {out_dir}")

    gm = gm_id_trend["gm_id"]

    # -----------------------------
    # Helper: Make and save a plot
    # -----------------------------
    def save_plot(y_key, ylabel, title, filename):
        plt.figure()
        plt.plot(gm, gm_id_trend[y_key], marker='o')
        plt.xlabel("gm/Id")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.grid(True)
        plt.locator_params(axis='x', nbins=20)
        plt.locator_params(axis='y', nbins=20)
        plt.tight_layout()
        filepath = os.path.join(out_dir, filename)
        plt.savefig(filepath, dpi=300)
        plt.close()

    # -----------------------------
    # Widths
    # -----------------------------
    save_plot("Wpass", "Wpass (µm)", "Pass Device Width vs gm/Id", "Wpass.png")
    save_plot("Wdiff", "Wdiff (µm)", "Diff Pair Width vs gm/Id", "Wdiff.png")
    save_plot("Wload", "Wload (µm)", "PMOS Load Width vs gm/Id", "Wload.png")

    # -----------------------------
    # gm values
    # -----------------------------
    save_plot("gm_pass", "gm_pass (uS)", "Pass Device gm vs gm/Id", "gm_pass.png")
    save_plot("gm_nmos", "gm_nmos (uS)", "Diff Pair gm vs gm/Id", "gm_nmos.png")
    save_plot("gm_pmos", "gm_pmos (uS)", "PMOS Load gm vs gm/Id", "gm_pmos.png")

    # -----------------------------
    # ro values
    # -----------------------------
    save_plot("ro_pass", "ro_pass (Ω)", "Pass Device ro vs gm/Id", "ro_pass.png")
    save_plot("ro_nmos", "ro_nmos (Ω)", "Diff Pair ro vs gm/Id", "ro_nmos.png")
    save_plot("ro_pmos", "ro_pmos (Ω)", "PMOS Load ro vs gm/Id", "ro_pmos.png")

    # -----------------------------
    # Lengths
    # -----------------------------
    save_plot("Ldiff", "Ldiff (µm)", "Chosen NMOS Length vs gm/Id", "Ldiff.png")
    save_plot("Lload", "Lload (µm)", "Chosen PMOS Length vs gm/Id", "Lload.png")

    # -----------------------------
    # AC Performance
    # -----------------------------
    save_plot("loopgain", "Loop Gain (linear)", "Loop Gain vs gm/Id", "loopgain.png")
    save_plot("fp1", "fp1 (KHz)", "Simulation fp1 vs gm/Id", "fp1_theoretical.png")
    save_plot("Iq_sim", "Iq_sim (uA)", "Simulated Iq vs gm/Id", "Iq_sim.png")
    save_plot("Power_sim", "Power_sim (uW)", "Simulated Power vs gm/Id", "Power_sim.png")
    
    # -----------------------------
    # Errors and PM
    # -----------------------------
    save_plot("loopgain_error", "Loop Gain Error (%)", "Loop Gain Error vs gm/Id", "loopgain_error.png")
    save_plot("fp1_error", "fp1 Error (%)", "fp1 Error vs gm/Id", "fp1_error.png")
    save_plot("phase_margin", "Phase Margin (deg)", "Phase Margin vs gm/Id", "phase_margin.png")
    save_plot("total_error", "Total Error (%)", "Total Error vs gm/Id", "total_error.png")

    ##print("[INFO] All plots saved.")
def all_in_saturation(op_file):
    """
    Checks if all devices in the LTSpice OP file are in saturation:
        |Vds| > |Vgs - Vth|

    Returns:
        dict: {
            "all_in_saturation": True/False,
            "m2_id_A": float or None,
            "m2_id_uA": float or None
        }
    """
    numeric_rows = {'Id', 'Vgs', 'Vds', 'Vth'}  # Only these rows are numeric
    op_values = {}

    with open(op_file, 'r') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("Name:"):
            # Extract device names from header
            devices = line.split()[1:]
            for dev in devices:
                if dev not in op_values:
                    op_values[dev] = {}

            # Read numeric rows following this header
            i += 1
            while i < len(lines):
                row_line = lines[i].strip()
                if not row_line or row_line.startswith("Name:"):
                    break
                parts = row_line.split()
                row_name = parts[0].strip(':')
                values = parts[1:]
                if len(values) != len(devices):
                    i += 1
                    continue
                if row_name in numeric_rows:
                    for dev, val in zip(devices, values):
                        try:
                            op_values[dev][row_name] = float(val.replace('D','e'))
                        except ValueError:
                            op_values[dev][row_name] = None
                i += 1
            continue
        i += 1

    # Check if all devices are in saturation
    all_sat = True
    for dev, vals in op_values.items():
        try:
            Vgs = vals['Vgs']
            Vds = vals['Vds']
            Vth = vals['Vth']
            if not (abs(Vds) > abs(Vgs - Vth)):
                all_sat = False
        except KeyError:
            all_sat = False

    # Get Id for m2 transistor
    Id = op_values.get('m2', {}).get('Id', None)

    result = {
        "all_in_saturation": all_sat,
        "m2_id_A": Id,
        "m2_id_uA": (Id*1e6) if Id is not None else None
    }

    ##print(result)
    return result

# -----------------------------
# Run LTspice in batch for .cir
# -----------------------------
def run_ltspice_cir(ltspice_exe, cir_file_path):
    """
    Runs LTspice on a .cir netlist in batch mode and returns the .raw file path
    """
    cmd = [ltspice_exe, '-b', cir_file_path]
    subprocess.run(cmd, check=True)
    raw_file = cir_file_path.replace(".cir", ".raw")
    if not os.path.exists(raw_file):
        raise FileNotFoundError(f"LTspice did not produce raw file: {raw_file}")
    # #print(f"Simulation complete. Raw file saved to {raw_file}")
    return raw_file

def get_low_freq_gain(raw_file):
    l = ltspice.Ltspice(raw_file)
    l.parse()
    freq = l.get_frequency()
    vout = l.get_data("V(out)")
    low_freq_idx = np.argmin(freq)
    gain_low = vout[low_freq_idx]
    gain_db = 20 * np.log10(np.abs(gain_low))
    return freq[low_freq_idx], gain_low, gain_db

def analyze_loopgain(raw_file, fp1_theo, loop_gain_theo):
    l = ltspice.Ltspice(raw_file)
    l.parse()
    freq = l.get_frequency()
    vout = l.get_data("V(out)")
    
    mag_db = 20 * np.log10(np.abs(vout))
    phase_deg = np.angle(vout, deg=True)
    # #print(mag_db)
    # #print(vout)
    # #print(freq)
    # #print("lowdb:",low_mag_db)
    low_mag_db = mag_db[0]
    minus3_db = low_mag_db - 3
    fp1_idx = np.argmin(np.abs(mag_db - minus3_db))
    fp1_sim = freq[fp1_idx]
    
    # -----------------------------
    # Find 0 dB crossover
    # -----------------------------
    zero_db_idx = np.argmin(np.abs(mag_db - 0))
    f0db_sim = freq[zero_db_idx]
    phase_at_0db = phase_deg[zero_db_idx]
    phase_margin_sim = phase_at_0db  # assuming negative feedback convention
    
    # #print("fp1theo:", fp1_theo)
    # #print("fp1sim:", fp1_sim)
    # #print(phase_margin_sim)
    loop_gain_error = (low_mag_db - loop_gain_theo)/loop_gain_theo * 100
    fp1_error = (fp1_theo - fp1_sim)/fp1_theo * 100
    
    return loop_gain_error, fp1_error, fp1_sim, f0db_sim, phase_margin_sim, low_mag_db, fp1_sim

# -----------------------------
# Load Specs
# -----------------------------
def best_gm_id_external(spec_file_name):
    df = pd.read_excel(spec_file_name)
    spec = df.set_index("Spec")["Value"].to_dict()

    dropout = float(spec["Vin"]) - float(spec["Vout"])
    loop_gain = 10 ** (spec["PSRR"] / 20)
    spec["dropout"] = dropout
    spec["loop_gain"] = loop_gain
    dropout = round(dropout, 3)
    fom = spec["fom"]
    it = spec["iterations"]
    # -----------------------------
    # Determine initial gm/Id sweep range
    # -----------------------------
    if dropout >= 1.8:
        vds = 1.8
    elif dropout >= 0.4:
        vds = 0.4
    else:
        vds = 0.2

    gm_id_start = 2/vds  # start value for sweep
    gm_id_end = MAX_GM_ID
    gm_id_vals = np.linspace(gm_id_start, gm_id_end, int(it))  # try 6 values

    best_gm_id = None
    min_error = np.inf
    best_results = None
    gm_id_trend = {
    "gm_id": [],
    "Wpass": [],
    "gm_pass": [],
    "ro_pass": [],
    "Wdiff": [],
    "gm_nmos": [],
    "ro_nmos": [],
    "Wload": [],
    "gm_pmos": [],
    "ro_pmos": [],
    "Ldiff": [],
    "Lload": [],
    "loopgain": [],
    "fp1": [],
    "loopgain_error": [],
    "fp1_error": [],
    "phase_margin": [],
    "total_error": [],
    "Iq_sim": [],
    "Power_sim":[]
    }

    for gm_id_target in gm_id_vals:
        # #print(f"\nTrying gm/Id target = {gm_id_target:.3f}")
        
        # -----------------------------
        # PMOS Pass FET sizing
        # -----------------------------
        gmro_file = build_filename("PGMRo", vds, "P")
        idw_file  = build_filename("PIDW", vds, "P")
        ft_file   = build_filename("PFT", vds, "P")
        
        gmro_df = pd.read_csv(gmro_file)
        idw_df  = pd.read_csv(idw_file)
        ft_df   = pd.read_csv(ft_file)

        gmro_vals  = gmro_df[f"{L_COL}_Y"].values
        gm_id_vals_table = gmro_df[f"{L_COL}_X"].values
        gmro_fun = interp1d(gm_id_vals_table, gmro_vals, fill_value="extrapolate")
        gmro = float(gmro_fun(gm_id_target))

        idw_vals  = idw_df[f"{L_COL}_Y"].values
        idw_fun   = interp1d(gm_id_vals_table, idw_vals, fill_value="extrapolate")
        idw = float(idw_fun(gm_id_target))
        
        Iload = float(spec["Iload|max"])
        gm = gm_id_target * Iload * 1000
        ro = (gmro * 10**6)/ gm
        W  = Iload * 1000/ idw
        ota_gain = spec["loop_gain"] / gmro
        wp1 = (10**6)/(spec["Cload"]*ro)
        fp1_theo = wp1 / (2 * np.pi)
        ota_gmro_needed = ota_gain * 2
        
        # #print("gmro:",gmro)
        # -----------------------------
        # OTA NMOS sizing
        # -----------------------------
        nmos_gmro_file = build_filename("NGMRo", vds, "N")
        nmos_idw_file  = build_filename("NIDW", vds, "N")
        nmos_gmro_df = pd.read_csv(nmos_gmro_file)
        nmos_idw_df  = pd.read_csv(nmos_idw_file)
        
        lengths = [float(col.replace("L___","").replace("nm_X",""))/1e3
                for col in nmos_gmro_df.columns if "_X" in col]
        lengths.sort()
        
        chosen_L = None
        for L in lengths:
            col_X = f"L___{int(L*1e3)}nm_X"
            col_Y = f"L___{int(L*1e3)}nm_Y"
            gmro_vals = nmos_gmro_df[col_Y].values
            gm_id_vals_table = nmos_gmro_df[col_X].values
            gmro_fun = interp1d(gm_id_vals_table, gmro_vals, fill_value="extrapolate")
            gmro_at_target = float(gmro_fun(gm_id_target))
            if gmro_at_target >= ota_gmro_needed:
                chosen_L = L
                break
        if chosen_L is None:
            continue
        
        col_X = f"L___{int(chosen_L*1e3)}nm_X"
        col_Y = f"L___{int(chosen_L*1e3)}nm_Y"
        idw_vals = nmos_idw_df[col_Y].values
        gm_id_vals_table = nmos_idw_df[col_X].values
        idw_fun = interp1d(gm_id_vals_table, idw_vals, fill_value="extrapolate")
        idw_chosen = float(idw_fun(gm_id_target))
        
        Iq = float(spec["Iquiescent"])
        Id = Iq/2
        gm_nmos = gm_id_target * Id
        ro_nmos = (gmro_at_target * 10**6)/ gm_nmos
        W_nmos  = Id / idw_chosen

        # -----------------------------
        # OTA PMOS Load sizing
        # -----------------------------
        pmos_gmro_file = build_filename("PGMRo", vds, "P")
        pmos_idw_file  = build_filename("PIDW", vds, "P")
        pmos_gmro_df = pd.read_csv(pmos_gmro_file)
        pmos_idw_df  = pd.read_csv(pmos_idw_file)
        
        # chosen_L_pmos = chosen_L
        lengths = [float(col.replace("L___","").replace("nm_X",""))/1e3
            for col in pmos_gmro_df.columns if "_X" in col]
        lengths.sort()

        chosen_L_pmos = None
        for L in lengths:
            col_X = f"L___{int(L*1e3)}nm_X"
            col_Y = f"L___{int(L*1e3)}nm_Y"
            gmro_vals = pmos_gmro_df[col_Y].values
            gm_id_vals = pmos_gmro_df[col_X].values
            gmro_fun = interp1d(gm_id_vals, gmro_vals, fill_value="extrapolate")
            gmro_at_target = float(gmro_fun(gm_id_target))
            if gmro_at_target >= ota_gmro_needed:
                chosen_L_pmos = L
                break

        if chosen_L_pmos is None:
            continue

        col_X = f"L___{int(chosen_L_pmos*1e3)}nm_X"
        col_Y = f"L___{int(chosen_L_pmos*1e3)}nm_Y"
        idw_vals = pmos_idw_df[col_Y].values
        gm_id_vals_table = pmos_idw_df[col_X].values
        idw_fun = interp1d(gm_id_vals_table, idw_vals, fill_value="extrapolate")
        idw_chosen_pmos = float(idw_fun(gm_id_target))
        
        Id_load = Iq/2
        gm_pmos = gm_id_target * Id_load
        ro_pmos = (gmro_at_target * 10**6)/ gm_pmos
        W_pmos  = Id_load / idw_chosen_pmos

        # -----------------------------
        # Run LTspice simulation
        # -----------------------------
        params = {
        "ibias": f"{Iq}u",
        "Iload": f"{Iload}m",
        "Wdiff": f"{W_nmos}u",
        "Wpass": f"{W}u",
        "Cload": f"{spec['Cload']}u",
        "Wload": f"{W_pmos}u",
        "Vin": spec["Vin"],
        "Vout": spec["Vout"],
        "l1": f"{chosen_L}u",
        "l2": f"{chosen_L_pmos}u"
        }
        raw_file = ASC_FILE.replace(".cir", ".raw")
        if os.path.exists(raw_file):
            os.remove(raw_file)
        modify_cir_params(ASC_FILE, params)
        raw_file = run_ltspice_cir(LTSPICE_PATH, ASC_FILE)
        meth = all_in_saturation(LOG_FILE)
        if meth["all_in_saturation"] == False:
            break
        # -----------------------------
        # Analyze results
        # -----------------------------
        loop_gain_error, fp1_error, fp1_sim, f0db_sim, phase_margin_sim, loopgain, fp1_val = analyze_loopgain(
            raw_file, fp1_theo, spec["PSRR"]
        )
        if fom == 1:
            total_error = loop_gain_error
        elif fom == 2:
            total_error = fp1_error
        
        gm_id_trend["gm_id"].append(gm_id_target)
        gm_id_trend["Wpass"].append(W)
        gm_id_trend["gm_pass"].append(gm)
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
        gm_id_trend["Iq_sim"].append(meth["m2_id_uA"])
        gm_id_trend["Power_sim"].append(meth["m2_id_uA"]*spec["Vin"])
        
        # #print(loop_gain_error)
        # #print(fp1_error)
        # #print(f"Total error = {total_error:.2f} %")
        
        if total_error < min_error and total_error > 0 and phase_margin_sim >= 45:
            min_error = total_error
            best_gm_id = gm_id_target
            best_results = {
                "Wpass": W,
                "Wdiff": W_nmos,
                "Wload": W_pmos,
                "gm_id": gm_id_target,
                "fp1_sim": fp1_sim,
                "phase_margin": phase_margin_sim,
                "loop_gain_error": loop_gain_error,
                "fp1_error": fp1_error,
                "Iq_sim": meth["m2_id_uA"],
                "Iq_error": (spec["Iquiescent"]/2 - meth["m2_id_uA"]) * 100 /spec["Iquiescent"],
                "Power": meth["m2_id_uA"] * spec["Vin"]
            }
    plot_trends(gm_id_trend, spec_file_name)
    # #print("\n===== Best gm/Id Results =====")
    # #print(best_results)
    return best_results

# best_gm_id_external("specs/spec1.xlsx")