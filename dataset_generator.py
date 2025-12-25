# import pandas as pd
# import copy
# import time
# from best_gm_id_external_bandwidth_max import best_gm_id_external_bandwidth
# from best_gm_id_internal_bandwidth_max import best_gm_id_internal_bandwidth

# # ==========================
# # USER CONFIGURATION
# # ==========================
# SPEC_CSV = "ldo_specs_5500.csv"
# OUT_CSV  = "ldo_specs_with_best_designs.csv"

# MAX_RETRIES = 5
# PSRR_RELAX_FACTOR = 0.95
# IQ_RELAX_FACTOR   = 2.00
# TD_RELAX_FACTOR   = 1.20
# IB_RELAX_FACTOR   = 2.00
# # ==========================
# # REQUIRED RESULT COLUMNS
# # ==========================
# RESULT_KEYS = [
#     "Wpass",
#     "Wdiff",
#     "Wload",
#     "gm_id",
#     "fp1_sim",
#     "phase_margin",
#     "loopgain",
#     "Iq_sim",
#     "Power",
#     "l1",
#     "l2"
# ]

# # ==========================
# # LOAD SPECS
# # ==========================
# df_specs = pd.read_csv(SPEC_CSV)

# final_rows = []

# df_subset = df_specs[:100]
# # ==========================
# # MAIN LOOP
# # ==========================
# for idx, spec_row in df_subset.iterrows():
#     print(f"\nProcessing row {idx+1}/{len(df_subset)}")

#     spec_base = spec_row.to_dict()
#     best_results = None
#     success = False

#     for attempt in range(MAX_RETRIES):
#         spec = copy.deepcopy(spec_base)

#         # ---------- RELAX SPECS ----------
#         if attempt > 0:
#             spec["PSRR"] *= (PSRR_RELAX_FACTOR ** attempt)
#             spec["Iquiescent"] *= (IQ_RELAX_FACTOR ** attempt)
#             spec["Transient Duration"] *= (TD_RELAX_FACTOR ** attempt)
#             spec["Iload|min"] *= (IB_RELAX_FACTOR ** attempt)

#         print(f"  Attempt {attempt+1} | PSRR={spec['PSRR']:.2f}, "
#               f"Iq={spec['Iquiescent']:.2f}uA")

#         # ---------- CALL APPROPRIATE FUNCTION ----------
#         if spec["LDO Type"] == "External":
#             best_results = best_gm_id_external_bandwidth(spec)
#         else:
#             best_results = best_gm_id_internal_bandwidth(spec)

#         if best_results is not None:
#             success = True
#             break

#     # ==========================
#     # MERGE RESULTS
#     # ==========================
#     final_row = spec_base.copy()

#     if success:
#         for key in RESULT_KEYS:
#             final_row[key] = best_results.get(key, None)
#         final_row["STATUS"] = "OK"
#         final_row["RETRIES_USED"] = attempt
#     else:
#         for key in RESULT_KEYS:
#             final_row[key] = None
#         final_row["STATUS"] = "FAILED"
#         final_row["RETRIES_USED"] = MAX_RETRIES

#     final_rows.append(final_row)

# # ==========================
# # SAVE FINAL DATASET
# # ==========================
# df_final = pd.DataFrame(final_rows)
# df_final.to_csv(OUT_CSV, index=False)

# print("\n===================================")
# print(" Completed gm/Id automation run")
# print(f" Output saved to: {OUT_CSV}")
# print("===================================")
import pandas as pd
import copy
import time
from best_gm_id_external_bandwidth_max import best_gm_id_external_bandwidth
from best_gm_id_internal_bandwidth_max import best_gm_id_internal_bandwidth

# ==========================
# USER CONFIGURATION
# ==========================
SPEC_CSV = "ldo_specs_5500.csv"
OUT_CSV  = "ldo_specs_with_best_designs.csv"

MAX_RETRIES = 1
PSRR_RELAX_FACTOR = 0.95
IQ_RELAX_FACTOR   = 3.00
TD_RELAX_FACTOR   = 1.20
IB_RELAX_FACTOR   = 3.00

# ==========================
# REQUIRED RESULT COLUMNS
# ==========================
RESULT_KEYS = [
    "Wpass", "Wdiff", "Wload", "gm_id", "fp1_sim",
    "phase_margin", "loopgain", "Iq_sim", "Power", "l1", "l2"
]

# ==========================
# LOAD SPECS
# ==========================
df_specs = pd.read_csv(SPEC_CSV)
df_subset = df_specs[1802:1900]
initial_idx = 1802
final_rows = []

try:
    # ==========================
    # MAIN LOOP
    # ==========================
    for idx, spec_row in df_subset.iterrows():
        print(f"\nProcessing row {idx+1}/{initial_idx+len(df_subset)}")

        spec_base = spec_row.to_dict()
        best_results = None
        success = False

        for attempt in range(MAX_RETRIES):
            spec = copy.deepcopy(spec_base)

            # ---------- RELAX SPECS ----------
            if attempt > 0:
                spec["PSRR"] *= (PSRR_RELAX_FACTOR ** attempt)
                spec["Iquiescent"] *= (IQ_RELAX_FACTOR ** attempt)
                spec["Transient Duration"] *= (TD_RELAX_FACTOR ** attempt)
                spec["Iload|min"] *= (IB_RELAX_FACTOR ** attempt)
                spec["Iload|max"] *= (IB_RELAX_FACTOR ** attempt)

            print(f"  Attempt {attempt+1} | PSRR={spec['PSRR']:.2f}, "
                  f"Iq={spec['Iquiescent']:.2f}uA")

            # ---------- CALL FUNCTION ----------
            if spec["LDO Type"] == "External":
                best_results = best_gm_id_external_bandwidth(spec)
            else:
                best_results = best_gm_id_internal_bandwidth(spec)

            if best_results is not None:
                success = True
                break

        # ---------- MERGE RESULTS ----------
        final_row = spec_base.copy()

        if success:
            for key in RESULT_KEYS:
                final_row[key] = best_results.get(key, None)
            final_row["STATUS"] = "OK"
            final_row["RETRIES_USED"] = attempt
        else:
            for key in RESULT_KEYS:
                final_row[key] = None
            final_row["STATUS"] = "FAILED"
            final_row["RETRIES_USED"] = MAX_RETRIES

        final_rows.append(final_row)

except KeyboardInterrupt:
    print("\n⚠️ KeyboardInterrupt detected! Saving partial results...")

except Exception as e:
    print("\n❌ Exception occurred:", str(e))
    print("Saving partial results before exiting...")

finally:
    # ==========================
    # ALWAYS SAVE WHAT WE HAVE
    # ==========================
    if final_rows:
        df_final = pd.DataFrame(final_rows)
        df_final.to_csv(OUT_CSV, index=False)
        print(f"\n✅ Partial data saved to: {OUT_CSV}")
        print(f"Rows saved: {len(final_rows)}")
    else:
        print("\n⚠️ No data to save.")

    print("===================================")
    print(" gm/Id automation terminated safely")
    print("===================================")
