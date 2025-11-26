import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
import os
import subprocess
import ltspice
import matplotlib.pyplot as plt

# -----------------------------
# Constants & Paths
# -----------------------------
MAX_GM_ID = 22
L_COL = "L___180nm"   # Only use length = 0.18 µm
BASE_PATH = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Techplots_180nm_2024"
CIR_FILE = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_loopgain_IIIT.cir"
LTSPICE_PATH = r"C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe"
PSRR_CIR_FILE = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_PSRR_IIIT.cir"
TRANS_CIR_FILE = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_Transient_IIIT.cir"
# -----------------------------
# Utility: Build CSV filenames dynamically
# -----------------------------
def build_filename(device, vds, n_or_p, W=5000):
    vds_str = str(vds).replace('.', 'p')
    filename = f"{device}_{n_or_p}GMID_VDS_{vds_str}V_W_{W}um.csv"
    return os.path.join(BASE_PATH, filename)

# -----------------------------
# Modify .param lines in .cir
# -----------------------------
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
            break
    else:
        new_line = param_line_identifier + " " + " ".join([f"{k}={v}" for k, v in param_dict.items()]) + "\n"
        lines.insert(0, new_line)

    with open(cir_file_path, 'w') as f:
        f.writelines(lines)
    
    print(f"Updated parameters in {cir_file_path}")
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
    print(f"Simulation complete. Raw file saved to {raw_file}")
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
# Plot loop gain vs frequency
# -----------------------------
def plot_loopgain(raw_file):
    l = ltspice.Ltspice(raw_file)
    l.parse()
    freq = l.get_frequency()
    vout = l.get_data("V(out)")
    vout_mag_db = 20 * np.log10(np.abs(vout))
    plt.figure(figsize=(8,5))
    plt.semilogx(freq, vout_mag_db, linewidth=2)
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlabel("Frequency [Hz]")
    plt.ylabel("V(out) Magnitude [dB]")
    plt.title("Loop Gain vs Frequency")
    plt.tight_layout()
    plt.show()
def plot_transient(raw_file):
    l = ltspice.Ltspice(raw_file)
    l.parse()
    time = l.get_time()
    vout = l.get_data("V(out)")
    plt.figure(figsize=(8,5))
    plt.semilogx(time, vout, linewidth=2)
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlabel("Time [Hz]")
    plt.ylabel("V(out)")
    plt.title("Loop Gain vs Frequency")
    plt.tight_layout()
    plt.show()

# -----------------------------
# Extract PSRR V(out)
# -----------------------------
def get_psrr_vout(raw_file):
    l = ltspice.Ltspice(raw_file)
    l.parse()
    freq = l.get_frequency()
    vout = l.get_data("V(out)")
    low_idx = np.argmin(freq)
    vout_low = vout[low_idx]
    vout_low_db = 20 * np.log10(np.abs(vout_low))
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
# Plot PSRR results
# -----------------------------
def plot_psrr_vout(psrr_results):
    freq = psrr_results["freq"]
    vout_mag_db = 20 * np.log10(np.abs(psrr_results["vout"]))
    plt.figure(figsize=(8,5))
    plt.semilogx(freq, vout_mag_db, linewidth=2)
    plt.scatter(psrr_results["low_freq_Hz"], psrr_results["vout_low_db"], color='red', label='Low Freq')
    plt.scatter(psrr_results["peak_freq_Hz"], psrr_results["vout_peak_db"], color='green', label='Peak')
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.xlabel("Frequency [Hz]")
    plt.ylabel("V(out) Magnitude [dB]")
    plt.title("PSRR V(out) vs Frequency")
    plt.legend()
    plt.tight_layout()
    plt.show()

# -----------------------------
# Example usage
# -----------------------------
params = {
    "ibias": "50u",
    "Iload": "10m",
    "Wdiff": "4.31u",
    "Wpass": "1132u",
    "Cload": "1u",
    "Wload": "2.7u",
    "Vin": "1.4",
    "Vout": "0.2",
    "l1": "0.72u",
    "l2": "0.18u"
}
# Update loopgain netlist and run
modify_cir_params(CIR_FILE, params)
raw_file = run_ltspice_cir(LTSPICE_PATH, CIR_FILE)
freq_low, vout_low, gain_db = get_low_freq_gain(raw_file)
print(f"Low-frequency V(out): {vout_low:.6f} V ({gain_db:.2f} dB) at {freq_low} Hz")
plot_loopgain(raw_file)

# Update PSRR netlist and run
modify_cir_params(PSRR_CIR_FILE, params)
raw_psrr_file = run_ltspice_cir(LTSPICE_PATH, PSRR_CIR_FILE)
psrr_results = get_psrr_vout(raw_psrr_file)
print(f"PSRR Low-frequency V(out): {psrr_results['vout_low_db']:.6f} dB at {psrr_results['low_freq_Hz']} Hz")
print(f"PSRR Peak V(out): {psrr_results['vout_peak_db']:.6f} dB at {psrr_results['peak_freq_Hz']} Hz")
plot_psrr_vout(psrr_results)

params["iload_min"] = "2m"
params["tdelay"] = "0"
params["trise"] = "1u"
params["tfall"] = "1u"
params["ton"] = "250u"
params["tperiod"] = "500u"
params["ncycles"] = "1000"
modify_cir_params(TRANS_CIR_FILE, params)
raw_file = run_ltspice_cir(LTSPICE_PATH, TRANS_CIR_FILE)
plot_transient(raw_file)

import re
import numpy as np

def all_in_saturation(op_file):
    op_text = open(op_file).read()
    """
    Returns True if ALL MOSFETs in the .op text are in saturation.
    Otherwise returns False.
    
    Uses: |Vds| > |Vgs - Vth|
    """
    
    # Regex for device rows like:
    # mpass  pmos292p  Id ...  Vgs ... Vds ... Vth ...
    device_pattern = re.compile(
        r"(?P<name>m\w*)\s+[\w\d]+\s+Id:\s*(?P<Id>[-+eE0-9\.]+)\s+Vgs:\s*(?P<Vgs>[-+eE0-9\.]+)\s+Vds:\s*(?P<Vds>[-+eE0-9\.]+)\s+Vbs:\s*[-+eE0-9\.]+\s+Vth:\s*(?P<Vth>[-+eE0-9\.]+)"
    )

    all_sat = True

    for match in device_pattern.finditer(op_text):
        Vgs = float(match.group("Vgs"))
        Vds = float(match.group("Vds"))
        Vth = float(match.group("Vth"))

        # Saturation check
        lhs = abs(Vds)
        rhs = abs(Vgs - Vth)

        if lhs < rhs:
            return False

    return True
print(all_in_saturation("C:/Users/SnigdhaYS/Documents/LTSpice_LDO_Automation/Externally_Compensated/Miller_LDO_Sim_Benches_502/LDO_loopgain_IIIT.log"))