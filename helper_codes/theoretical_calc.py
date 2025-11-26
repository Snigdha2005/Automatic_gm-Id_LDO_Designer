import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
import os

# -----------------------------
# Constants & Paths
# -----------------------------
MAX_GM_ID = 22
L_COL = "L___180nm"   # Only use length = 0.18 µm
BASE_PATH = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Techplots_180nm_2024"

# -----------------------------
# Load Specs
# -----------------------------
df = pd.read_excel("specs/spec1.xlsx")
spec = df.set_index("Spec")["Value"].to_dict()

if float(spec["External"]) != 1:
    raise ValueError("Only External=1 case supported.")

dropout = float(spec["Vin"]) - float(spec["Vout"])
loop_gain = 10 ** (spec["PSRR"] / 20)
spec["dropout"] = dropout
spec["loop_gain"] = loop_gain
dropout = round(dropout, 3)

# -----------------------------
# Set gm/Id target and VDS for PMOS based on dropout
# -----------------------------
if dropout >= 1.8:
    gm_id_target = 2
    vds_for_gmro = 1.8
    vds_for_idw  = 1.8
    vds_for_ft   = 1.8
elif dropout >= 0.4:
    gm_id_target = 10
    vds_for_gmro = 0.4
    vds_for_idw  = 0.4
    vds_for_ft   = 0.4
elif dropout >= 0.2:
    gm_id_target = 20
    vds_for_gmro = 0.2
    vds_for_idw  = 0.2
    vds_for_ft   = 0.2
else:
    gm_id_target = MAX_GM_ID
    vds_for_gmro = 0.2
    vds_for_idw  = 0.2
    vds_for_ft   = 0.2

print(f"Dropout: {dropout}, Initial gm/Id target: {gm_id_target}")

# -----------------------------
# Utility: Build CSV filenames dynamically
# -----------------------------
def build_filename(device, vds, n_or_p, W=5000):
    """Construct CSV path based on device, VDS, and width"""
    vds_str = str(vds).replace('.', 'p')
    filename = f"{device}_{n_or_p}GMID_VDS_{vds_str}V_W_{W}um.csv"
    return os.path.join(BASE_PATH, filename)

# -----------------------------
# Load PMOS CSVs
# -----------------------------
gmro_file = build_filename("PGMRo", vds_for_gmro, "P")
idw_file  = build_filename("PIDW", vds_for_idw, "P")
ft_file   = build_filename("PFT", vds_for_ft, "P")

gmro_df = pd.read_csv(gmro_file)
idw_df  = pd.read_csv(idw_file)
ft_df   = pd.read_csv(ft_file)

# Extract L = 0.18um columns
gm_id_vals = gmro_df[f"{L_COL}_X"].values
gmro_vals  = gmro_df[f"{L_COL}_Y"].values
idw_vals   = idw_df[f"{L_COL}_Y"].values
ft_vals    = ft_df[f"{L_COL}_Y"].values

# -----------------------------
# Interpolation functions
# -----------------------------
gmro_fun = interp1d(gm_id_vals, gmro_vals, fill_value="extrapolate")
idw_fun  = interp1d(gm_id_vals, idw_vals, fill_value="extrapolate")
ft_fun   = interp1d(gm_id_vals, ft_vals, fill_value="extrapolate")

gmro = float(gmro_fun(gm_id_target))
idw  = float(idw_fun(gm_id_target))
ft   = float(ft_fun(gm_id_target))

# -----------------------------
# PMOS Pass FET sizing
# -----------------------------
Iload = float(spec["Iload|max"])

gm = gm_id_target * Iload
ro = gmro / gm
W  = Iload / idw
ota_gain = spec["loop_gain"] / gmro
cgs_cgd = gm / (2 * np.pi * ft)
wp1 = (10**6)/(spec["Cload"]*ro)
wp2 = loop_gain * wp1
fp1 = wp1 / (2 * np.pi)
ota_gmro_needed = ota_gain * 2
rodiff = 1 / (wp2 * cgs_cgd)

print("\n===== PMOS Pass FET Results (L = 0.18um) =====")
print("gm/Id (target)        =", gm_id_target)
print("gm·ro                 =", gmro)
print("Id/W (A/um)           =", idw)
print("gm (A/V)              =", gm)
print("ro (Ohm)              =", ro)
print("Width W (um)          =", W)
print("fT (Hz)               =", ft)
print("OTA gain = loop_gain/gmro =", ota_gain)
print("================================================")

# -----------------------------
# OTA NMOS sizing
# -----------------------------

# Load NMOS CSVs dynamically
nmos_gmro_file = build_filename("NGMRo", vds_for_gmro, "N")
nmos_idw_file  = build_filename("NIDW", vds_for_idw, "N")

nmos_gmro_df = pd.read_csv(nmos_gmro_file)
nmos_idw_df  = pd.read_csv(nmos_idw_file)

# Determine available lengths from columns
lengths = [float(col.replace("L___","").replace("nm_X",""))/1e3
           for col in nmos_gmro_df.columns if "_X" in col]
lengths.sort()

# Find minimal L satisfying ota_gmro_needed at target gm/Id
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

# Get Id/W for chosen length
col_X = f"L___{int(chosen_L*1e3)}nm_X"
col_Y = f"L___{int(chosen_L*1e3)}nm_Y"
idw_vals = nmos_idw_df[col_Y].values
gm_id_vals = nmos_idw_df[col_X].values
idw_fun = interp1d(gm_id_vals, idw_vals, fill_value="extrapolate")
idw_chosen = float(idw_fun(gm_id_target))

# OTA sizing calculations
Iq = float(spec["Iload|max"])
Id = Iq / 2  # half tail current per branch
gm_nmos = gm_id_target * Id
ro_nmos = gmro_at_target / gm_nmos
W_nmos  = Id / idw_chosen

print("\n===== OTA NMOS Sizing =====")
print("gm/Id (target)  =", gm_id_target)
print("Chosen L (um)   =", chosen_L)
print("gm·ro           =", gmro_at_target)
print("Id/W (A/um)     =", idw_chosen)
print("gm (A/V)        =", gm_nmos)
print("ro (Ohm)        =", ro_nmos)
print("Width W (um)    =", W_nmos)
print("=================================")

# -----------------------------
# OTA PMOS Load Sizing
# -----------------------------

# Load PMOS CSVs dynamically for OTA load
pmos_gmro_file = build_filename("PGMRo", vds_for_gmro, "P")
pmos_idw_file  = build_filename("PIDW", vds_for_idw, "P")

pmos_gmro_df = pd.read_csv(pmos_gmro_file)
pmos_idw_df  = pd.read_csv(pmos_idw_file)

# Determine available lengths from columns
lengths = [float(col.replace("L___","").replace("nm_X",""))/1e3
           for col in pmos_gmro_df.columns if "_X" in col]
lengths.sort()

# Find minimal L satisfying ota_gmro_needed at target gm/Id
chosen_L_pmos = None
for L in lengths:
    col_X = f"L___{int(L*1e3)}nm_X"
    col_Y = f"L___{int(L*1e3)}nm_Y"
    gmro_vals = pmos_gmro_df[col_Y].values
    gm_id_vals = pmos_gmro_df[col_X].values
    gmro_fun = interp1d(gm_id_vals, gmro_vals, fill_value="extrapolate")
    gmro_at_target = float(gmro_fun(gm_id_target))
    
    # Choose the length closest to the required gmro
    if gmro_at_target >= ota_gmro_needed:
        chosen_L_pmos = L
        break

if chosen_L_pmos is None:
    raise ValueError("No PMOS length satisfies gmro requirement.")

# Get Id/W for chosen length
col_X = f"L___{int(chosen_L_pmos*1e3)}nm_X"
col_Y = f"L___{int(chosen_L_pmos*1e3)}nm_Y"
idw_vals = pmos_idw_df[col_Y].values
gm_id_vals = pmos_idw_df[col_X].values
idw_fun = interp1d(gm_id_vals, idw_vals, fill_value="extrapolate")
idw_chosen_pmos = float(idw_fun(gm_id_target))

# OTA PMOS load sizing calculations
Iq = float(spec["Iload|max"])
Id_load = Iq / 2  # PMOS load branch current
gm_pmos = gm_id_target * Id_load
ro_pmos = gmro_at_target / gm_pmos
W_pmos  = Id_load / idw_chosen_pmos

print("\n===== OTA PMOS Load Sizing =====")
print("gm/Id (target)  =", gm_id_target)
print("Chosen L (um)   =", chosen_L_pmos)
print("gm·ro           =", gmro_at_target)
print("Id/W (A/um)     =", idw_chosen_pmos)
print("gm (A/V)        =", gm_pmos)
print("ro (Ohm)        =", ro_pmos)
print("Width W (um)    =", W_pmos)
print("=================================")
