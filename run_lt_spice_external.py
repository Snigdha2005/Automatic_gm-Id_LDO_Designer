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
LTSPICE_PATH = r"C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe"
PSRR_ASC_FILE = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_PSRR_IIIT.cir"
TRANS_ASC_FILE = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_Transient_IIIT.cir"
LOG_FILE = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_loopgain_IIIT.log"

# -----------------------------
# Utility: Build CSV filenames dynamically
# -----------------------------
def build_filename(device, vds, n_or_p, W=5000):
    vds_str = str(vds).replace('.', 'p')
    filename = f"{device}_{n_or_p}GMID_VDS_{vds_str}V_W_{W}um.csv"
    return os.path.join(BASE_PATH, filename)
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

    #print(result)
    return result

def run_temperature_sweep(spec_file_name, cir_file_path, ltspice_exe, params, temps=[-40, 27, 125]):
    """
    Run LTspice temperature sweep on the given .cir file, plot loopgain for all temperatures,
    compute Iq and power, and save loopgain, fp1, phase margin, Iq and power in a text file.
    """
    base = os.path.basename(spec_file_name)        # spec1.xlsx
    folder = os.path.splitext(base)[0]             # spec1
    out_dir = os.path.join(os.path.dirname(spec_file_name), folder)
    os.makedirs(out_dir, exist_ok=True)
    vout_all = []
    loopgain_txt_lines = []
    for i in temps:
        # Add temperature sweep line to .cir
        with open(cir_file_path, 'r') as f:
            lines = f.readlines()
        
        # Remove existing .temp lines if present
        lines = [line for line in lines if not line.lower().startswith(".temp")]
        
        # Insert new .temp line after title/comments (usually after first line)
        lines.insert(1, ".temp " + str(i) + "\n")
        
        with open(cir_file_path, 'w') as f:
            f.writelines(lines)
        
        # Update parameters in .cir
        modify_cir_params(cir_file_path, params)
        
        # Run LTspice batch simulation
        raw_file = run_ltspice_cir(ltspice_exe, cir_file_path)
        # Parse raw file
        l = ltspice.Ltspice(raw_file)
        l.parse()
        freq = l.get_frequency()
        l1 = ltspice.Ltspice("C:/Users/SnigdhaYS/Documents/LTSpice_LDO_Automation/Externally_Compensated/Miller_LDO_Sim_Benches_502/LDO_loopgain_IIIT.op.raw")
        l1.parse()
        
        # Nominal values at 27°C for error calculation
        Iq_nom = float(params["ibias"][:len(params["ibias"])-1])/2
        P_nom = Iq_nom*float(params["Vin"])
        
        vout = l.get_data("V(out)")
        vout_all.append(vout)
        
        mag_db = 20*np.log10(np.abs(vout))
        
        loopgain = mag_db[0]
        #print("loopgain", loopgain)
        minus3_db = loopgain - 3
        fp1_idx = np.argmin(np.abs(mag_db - minus3_db))
        fp1 = freq[fp1_idx]
        #print("fp1", fp1)
        zero_db_idx = np.argmin(np.abs(mag_db - 0))
        phase_deg = np.angle(vout, deg=True)
        phase_margin = phase_deg[zero_db_idx]
        #print("pm", phase_margin)
        Iq_A = l1.get_data("Id(M2)")[0]
        Iq_uA = Iq_A * 1e6 if Iq_A is not None else None
        #print("iq", Iq_uA)
        Vin = float(params["Vin"])
        P = Vin * Iq_uA if Iq_A is not None else None
        Iq_error = ((-Iq_uA + Iq_nom)/Iq_nom * 100) if Iq_A is not None and Iq_nom is not None else None
        P_error = ((-P + P_nom)/P_nom * 100) if P is not None and P_nom is not None else None
        #print(Iq_error)
        #print(P)
        #print(P_error)
        
        loopgain_txt_lines.append(
            f"T={i}°C : Loop Gain={loopgain:.2f} dB, fp1={fp1:.2f} Hz, Phase Margin={phase_margin:.2f} deg, "
            f"Iq={Iq_uA:.2f} uA, Iq_error={Iq_error:.2f}%, Power={P*1e3:.2f} mW, Power_error={P_error:.2f}%"
        )
    lines = [line for line in lines if not line.lower().startswith(".temp")]
        
    # Save plot
    plt.figure(figsize=(8,5))
    colors = ['b', 'g', 'r']
    for i, T in enumerate(temps):
        mag_db = 20*np.log10(np.abs(vout_all[i]))
        plt.semilogx(freq, mag_db, color=colors[i], label=f"{T}°C")
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlabel("Frequency [Hz]")
    plt.ylabel("V(out) Magnitude [dB]")
    plt.title("Loop Gain vs Frequency (Temperature Sweep)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "temp_change.png"), dpi=150)
    
    # Save text file
    txt_file = os.path.join(out_dir, "temp_loopgain.txt")
    with open(txt_file, 'w') as f:
        f.write("\n".join(loopgain_txt_lines))
    
    # print(f"Temperature sweep done. Plot saved as temp_change.png and data in temp_loopgain.txt")


# -----------------------------
# Modify .param lines in .cir
# -----------------------------
def modify_cir_params(cir_file_path, param_dict, param_line_identifier=".param"):
    """
    Updates the .param line in a .cir SPICE file with new values.
    """
    with open(cir_file_path, 'r') as f:
        lines = f.readlines()
    
    # with open(ASC_FILE, 'r') as f:
    #     print("".join(f.readlines()))
    for i, line in enumerate(lines):
        if line.strip().startswith(param_line_identifier):
            # print(line)
            parts = line.strip().split()[1:]
            # print(parts)
            if len(parts) > 1:
                parts = ["".join(parts)]
            # print(parts)
            for j, part in enumerate(parts):
                key, _ = part.split("=")
                if key in param_dict:
                    parts[j] = f"{key}={param_dict[key]}"
            lines[i] = param_line_identifier + " " + " ".join(parts) + "\n"
    # else:
    #     new_line = param_line_identifier + " " + " ".join([f"{k}={v}" for k, v in param_dict.items()]) + "\n"
    #     lines.insert(0, new_line)

    with open(cir_file_path, 'w') as f:
        f.writelines(lines)
    # with open(ASC_FILE, 'r') as f:
    #     print("".join(f.readlines()))

    # print(f"Updated parameters in {cir_file_path}")
    return cir_file_path

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
    # print(f"Simulation complete. Raw file saved to {raw_file}")
    return raw_file

# -----------------------------
# Extract low-frequency V(out)
# -----------------------------
def get_low_freq_gain(raw_file):
    l = ltspice.Ltspice(raw_file)
    l.parse()
    freq = l.get_frequency()
    vout = l.get_data("V(out)")
    low_freq_idx = np.argmin(freq)
    gain_low = vout[low_freq_idx]
    gain_db = 20 * np.log10(np.abs(gain_low))
    return freq[low_freq_idx], gain_low, gain_db

# -----------------------------
# Plot Loop Gain vs Frequency
# -----------------------------
def plot_loopgain(spec_file_name, raw_file):
    l = ltspice.Ltspice(raw_file)
    l.parse()

    freq = l.get_frequency()          # Frequency array in Hz
    vout = l.get_data("V(out)")       # Complex AC response

    # Magnitude in dB
    vout_mag_db = 20 * np.log10(np.abs(vout))

    # Plot
    plt.figure(figsize=(8,5))
    plt.semilogx(freq, vout_mag_db, linewidth=2)
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlabel("Frequency [Hz]")
    plt.ylabel("V(out) Magnitude [dB]")
    plt.title("Loop Gain vs Frequency")
    plt.tight_layout()
    base = os.path.basename(spec_file_name)        # spec1.xlsx
    folder = os.path.splitext(base)[0]             # spec1
    out_dir = os.path.join(os.path.dirname(spec_file_name), folder)
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, "loopgain.png")
    plt.savefig(filepath, dpi=150)
    # plt.show()

def plot_transient(spec_file_name, raw_file):
    l = ltspice.Ltspice(raw_file)
    l.parse()

    time = l.get_time()          # Frequency array in Hz
    vout = l.get_data("V(out)")       # Complex AC response

    # Magnitude in dB
    # vout_mag_db = 20 * np.log10(np.abs(vout))

    # Plot
    plt.figure(figsize=(8,5))
    plt.semilogx(time, vout, linewidth=0.2)
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlabel("Time")
    plt.ylabel("V(out)")
    plt.title("V(out) vs Time")
    plt.tight_layout()
    
    base = os.path.basename(spec_file_name)        # spec1.xlsx
    folder = os.path.splitext(base)[0]             # spec1
    out_dir = os.path.join(os.path.dirname(spec_file_name), folder)
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, "transient.png")
    plt.savefig(filepath, dpi=150)
    # plt.show()

# Extract V(out) magnitude, low freq and peak
def get_psrr_vout(raw_file):
    l = ltspice.Ltspice(raw_file)
    l.parse()
    freq = l.get_frequency()
    vout = l.get_data("V(out)")
    
    # Low frequency
    low_idx = np.argmin(freq)
    vout_low = vout[low_idx]
    vout_low_db = 20 * np.log10(np.abs(vout_low))
    # Peak value
    peak_idx = np.argmax(np.abs(vout))
    vout_peak = vout[peak_idx]
    vout_peak_db = 20 * np.log10(np.abs(vout_peak))
    return {
        "freq": freq,
        "vout": vout,
        "low_freq_val": vout_low,
        "low_freq_Hz": freq[low_idx],
        "peak_val": vout_peak,
        "peak_freq_Hz": freq[peak_idx],
        "vout_low_db":vout_low_db,
        "vout_peak_db":vout_peak_db
    }

# -----------------------------
# Plot PSRR V(out) magnitude
# -----------------------------
def plot_psrr_vout(spec_file_name, psrr_results):
    freq = psrr_results["freq"]
    vout_mag_db = 20 * np.log10(np.abs(psrr_results["vout"]))
    
    plt.figure(figsize=(8,5))
    plt.semilogx(freq, vout_mag_db, linewidth=2)
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlabel("Frequency [Hz]")
    plt.ylabel("V(out) Magnitude [dB]")
    plt.title("PSRR V(out) vs Frequency")
    
    # Mark low-frequency and peak points
    plt.scatter(psrr_results["low_freq_Hz"], 20*np.log10(np.abs(psrr_results["low_freq_val"])),
                color='red', label='Low Freq')
    plt.scatter(psrr_results["peak_freq_Hz"], 20*np.log10(np.abs(psrr_results["peak_val"])),
                color='green', label='Peak')
    plt.legend()
    plt.tight_layout()
    base = os.path.basename(spec_file_name)        # spec1.xlsx
    folder = os.path.splitext(base)[0]             # spec1
    out_dir = os.path.join(os.path.dirname(spec_file_name), folder)
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, "psrr.png")
    plt.savefig(filepath, dpi=150)
    # plt.show()

# -----------------------------
# Load Specs
# -----------------------------
def run_lt_spice_external(spec_file_name, gm_id_best):
    df = pd.read_excel(spec_file_name)
    spec = df.set_index("Spec")["Value"].to_dict()

    if float(spec["External"]) != 1:
        raise ValueError("Only External=1 case supported.")

    dropout = float(spec["Vin"]) - float(spec["Vout"])
    loop_gain = 10 ** (spec["PSRR"] / 20)
    spec["dropout"] = dropout
    spec["loop_gain"] = loop_gain
    dropout = round(dropout, 3)
    # print(spec)
    # -----------------------------
    # Set gm/Id target and VDS for PMOS based on dropout
    # -----------------------------
    if dropout >= 1.8:
        gm_id_target = gm_id_best
        vds_for_gmro = 1.8
        vds_for_idw  = 1.8
        vds_for_ft   = 1.8
    elif dropout >= 0.4:
        gm_id_target = gm_id_best
        vds_for_gmro = 0.4
        vds_for_idw  = 0.4
        vds_for_ft   = 0.4
    elif dropout >= 0.2:
        gm_id_target = gm_id_best
        vds_for_gmro = 0.2
        vds_for_idw  = 0.2
        vds_for_ft   = 0.2
    else:
        gm_id_target = MAX_GM_ID
        vds_for_gmro = 0.2
        vds_for_idw  = 0.2
        vds_for_ft   = 0.2

    # print(f"Dropout: {dropout}, Initial gm/Id target: {gm_id_target}")

    # -----------------------------
    # PMOS Pass FET sizing
    # -----------------------------
    gmro_file = build_filename("PGMRo", vds_for_gmro, "P")
    idw_file  = build_filename("PIDW", vds_for_idw, "P")
    ft_file   = build_filename("PFT", vds_for_ft, "P")

    gmro_df = pd.read_csv(gmro_file)
    idw_df  = pd.read_csv(idw_file)
    ft_df   = pd.read_csv(ft_file)

    gm_id_vals = gmro_df[f"{L_COL}_X"].values
    gmro_vals  = gmro_df[f"{L_COL}_Y"].values
    idw_vals   = idw_df[f"{L_COL}_Y"].values
    ft_vals    = ft_df[f"{L_COL}_Y"].values

    gmro_fun = interp1d(gm_id_vals, gmro_vals, fill_value="extrapolate")
    idw_fun  = interp1d(gm_id_vals, idw_vals, fill_value="extrapolate")
    ft_fun   = interp1d(gm_id_vals, ft_vals, fill_value="extrapolate")

    gmro = float(gmro_fun(gm_id_target))
    idw  = float(idw_fun(gm_id_target))
    ft   = float(ft_fun(gm_id_target))

    Iload = float(spec["Iload|max"])
    gm = gm_id_target * Iload * 1000
    ro = (gmro * 10**6)/ gm
    W  = Iload *1000 / idw
    ota_gain = spec["loop_gain"] / gmro
    cgs_cgd = gm / (2 * np.pi * ft)
    wp1 = (10**6)/(spec["Cload"]*ro)
    wp2 = loop_gain * wp1
    fp1 = wp1 / (2 * np.pi)
    ota_gmro_needed = ota_gain * 2
    rodiff = 1 / (wp2 * cgs_cgd)

    # print("\n===== PMOS Pass FET Results (L = 0.18um) =====")
    # print("gm/Id (target)        =", gm_id_target)
    # print("gm·ro                 =", gmro)
    # print("Id/W (A/um)           =", idw)
    # print("gm (A/V)              =", gm)
    # print("ro (Ohm)              =", ro)
    # print("Width W (um)          =", W)
    # print("fT (Hz)               =", ft)
    # print("OTA gain = loop_gain/gmro =", ota_gain)
    # print("================================================")
    # print("ota_gmro needed:", ota_gmro_needed)
    # -----------------------------
    # OTA NMOS sizing
    # -----------------------------
    nmos_gmro_file = build_filename("NGMRo", vds_for_gmro, "N")
    nmos_idw_file  = build_filename("NIDW", vds_for_idw, "N")

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
        gm_id_vals = nmos_gmro_df[col_X].values
        gmro_fun = interp1d(gm_id_vals, gmro_vals, fill_value="extrapolate")
        gmro_at_target = float(gmro_fun(gm_id_target))
        if gmro_at_target >= ota_gmro_needed:
            chosen_L = L
            break

    if chosen_L is None:
        raise ValueError("No NMOS length satisfies gmro requirement.")

    col_X = f"L___{int(chosen_L*1e3)}nm_X"
    col_Y = f"L___{int(chosen_L*1e3)}nm_Y"
    idw_vals = nmos_idw_df[col_Y].values
    gm_id_vals = nmos_idw_df[col_X].values
    idw_fun = interp1d(gm_id_vals, idw_vals, fill_value="extrapolate")
    idw_chosen = float(idw_fun(gm_id_target))

    Iq = float(spec["Iquiescent"])
    Id = Iq / 2
    gm_nmos = gm_id_target * Id
    ro_nmos = gmro_at_target / gm_nmos
    W_nmos  = Id / idw_chosen

    # print("\n===== OTA NMOS Sizing =====")
    # print("gm/Id (target)  =", gm_id_target)
    # print("Chosen L (um)   =", chosen_L)
    # print("gm·ro           =", gmro_at_target)
    # print("Id/W (A/um)     =", idw_chosen)
    # print("gm (A/V)        =", gm_nmos)
    # print("ro (Ohm)        =", ro_nmos)
    # print("Width W (um)    =", W_nmos)
    # print("=================================")

    # -----------------------------
    # OTA PMOS Load sizing
    # -----------------------------
    pmos_gmro_file = build_filename("PGMRo", vds_for_gmro, "P")
    pmos_idw_file  = build_filename("PIDW", vds_for_idw, "P")

    pmos_gmro_df = pd.read_csv(pmos_gmro_file)
    pmos_idw_df  = pd.read_csv(pmos_idw_file)

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
        raise ValueError("No PMOS length satisfies gmro requirement.")

    col_X = f"L___{int(chosen_L_pmos*1e3)}nm_X"
    col_Y = f"L___{int(chosen_L_pmos*1e3)}nm_Y"
    idw_vals = pmos_idw_df[col_Y].values
    gm_id_vals = pmos_idw_df[col_X].values
    idw_fun = interp1d(gm_id_vals, idw_vals, fill_value="extrapolate")
    idw_chosen_pmos = float(idw_fun(gm_id_target))

    Id_load = Iq / 2
    gm_pmos = gm_id_target * Id_load
    ro_pmos = gmro_at_target / gm_pmos
    W_pmos  = Id_load / idw_chosen_pmos

    # print("\n===== OTA PMOS Load Sizing =====")
    # print("gm/Id (target)  =", gm_id_target)
    # print("Chosen L (um)   =", chosen_L_pmos)
    # print("gm·ro           =", gmro_at_target)
    # print("Id/W (A/um)     =", idw_chosen_pmos)
    # print("gm (A/V)        =", gm_pmos)
    # print("ro (Ohm)        =", ro_pmos)
    # print("Width W (um)    =", W_pmos)
    # print("=================================")


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
    # print(params)
    raw_file = ASC_FILE.replace(".cir", ".raw")
    if os.path.exists(raw_file):
        os.remove(raw_file)
    modify_cir_params(ASC_FILE, params)
    raw_file = run_ltspice_cir(LTSPICE_PATH, ASC_FILE)
    meth = all_in_saturation(LOG_FILE)
    if meth["all_in_saturation"] == False:
            return {}
    freq_low, vout_low, gain_db = get_low_freq_gain(raw_file)
    # print(f"\nLow-frequency V(out): {vout_low:.6f} V ({gain_db:.2f} dB) at {freq_low} Hz")
    plot_loopgain(spec_file_name, raw_file)

    modify_cir_params(PSRR_ASC_FILE, params)

    raw_psrr_file = run_ltspice_cir(LTSPICE_PATH, PSRR_ASC_FILE)

    psrr_results = get_psrr_vout(raw_psrr_file)

    # print(f"\nPSRR Low-frequency V(out): {psrr_results['vout_low_db']:.6f} dB at {psrr_results['low_freq_Hz']} Hz")
    # print(f"PSRR Peak V(out): {psrr_results['vout_peak_db']:.6f} dB at {psrr_results['peak_freq_Hz']} Hz")


    plot_psrr_vout(spec_file_name, psrr_results)
    params["iload_min"] = f"{spec['iload_min']}m"
    params["tdelay"] = f"{spec['tdelay']}u"
    params["trise"] = f"{spec['trise']}u"
    params["tfall"] = f"{spec['tfall']}u"
    params["ton"] = f"{spec['ton']}u"
    params["tperiod"] = f"{spec['tperiod']}u"
    params["ncycles"] = f"{spec['ncycles']}"
    params["Iq_sim"] = meth["m2_id_uA"]
    modify_cir_params(TRANS_ASC_FILE, params)
    raw_trans_file = run_ltspice_cir(LTSPICE_PATH, TRANS_ASC_FILE)
    plot_transient(spec_file_name, raw_trans_file)
    # -----------------------------
    # Analyze Loop Gain Simulation
    # -----------------------------
    def analyze_loopgain(raw_file, fp1_theo=fp1, loop_gain_theo=spec["PSRR"]):
        l = ltspice.Ltspice(raw_file)
        l.parse()
        freq = l.get_frequency()
        vout = l.get_data("V(out)")
        
        # Magnitude in dB
        mag_db = 20 * np.log10(np.abs(vout))
        
        # Phase in degrees
        phase_deg = np.angle(vout, deg=True)
        
        # -----------------------------
        # Find -3 dB frequency relative to low-frequency gain
        # -----------------------------
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
        
        # -----------------------------
        # Calculate errors vs theoretical
        # -----------------------------
        loop_gain_sim = low_mag_db
        loop_gain_error = abs(loop_gain_sim - loop_gain_theo)/loop_gain_theo * 100
        fp1_error = abs(fp1_sim - fp1_theo)/fp1_theo * 100
        
        print("\n===== Loop Gain Simulation Analysis =====")
        print(f"Low-frequency loop gain: {loop_gain_sim:.2f} (theo: {loop_gain_theo:.2f}) -> Error: {loop_gain_error:.2f} %")
        print(f"fp1 (-3 dB frequency): {fp1_sim:.2f} Hz (theo: {fp1_theo:.2f} Hz) -> Error: {fp1_error:.2f} %")
        print(f"0 dB crossover frequency: {f0db_sim:.2f} Hz")
        print(f"Phase at 0 dB: {phase_at_0db:.2f} deg -> Phase margin: {phase_margin_sim:.2f} deg")
        
        return {
            "freq": freq,
            "mag_db": mag_db,
            "phase_deg": phase_deg,
            "fp1_sim": fp1_sim,
            "f0db_sim": f0db_sim,
            "phase_margin_sim": phase_margin_sim,
            "loop_gain_error": loop_gain_error,
            "fp1_error": fp1_error,
            "loop_gain":low_mag_db
            
        }
    run_temperature_sweep(spec_file_name,ASC_FILE,LTSPICE_PATH,params)
    
    loopgain_analysis = analyze_loopgain(raw_file)
    combined = {**loopgain_analysis, ** params}
    return combined
    # -----------------------------
    # Optional: Plot loop gain magnitude with fp1 and 0 dB markers
    # -----------------------------
    # plt.figure(figsize=(8,5))
    # plt.semilogx(loopgain_analysis["freq"], loopgain_analysis["mag_db"], linewidth=2)
    # plt.grid(True, which='both', linestyle='--', alpha=0.5)
    # plt.xlabel("Frequency [Hz]")
    # plt.ylabel("Loop Gain Magnitude [dB]")
    # plt.title("Loop Gain Analysis")
    # plt.scatter(loopgain_analysis["fp1_sim"], 
    #             20*np.log10(spec["loop_gain"]), color='red', label='fp1 -3dB')
    # plt.scatter(loopgain_analysis["f0db_sim"], 0, color='green', label='0 dB crossover')
    # plt.legend()
    # plt.tight_layout()
    # plt.show()
run_lt_spice_external("C:/Users/SnigdhaYS/Documents/LTSpice_LDO_Automation/specs/spec1.xlsx", 10)