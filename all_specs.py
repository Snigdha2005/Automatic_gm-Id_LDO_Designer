# import os
# import pandas as pd

# from best_gm_id_external import best_gm_id_external
# from best_gm_id_internal import best_gm_id_internal
# from run_lt_spice_external import run_lt_spice_external
# from run_lt_spice_internal import run_lt_spice_internal

# SPEC_FOLDER = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\specs"


# def run_all_specs():

#     for file in os.listdir(SPEC_FOLDER):

#         if not file.endswith(".xlsx"):
#             continue

#         spec_path = os.path.join(SPEC_FOLDER, file)
#         print(f"\n=============================")
#         print(f"Processing spec: {file}")
#         print(f"=============================")

#         # ------------------------------
#         # Load spec file
#         # ------------------------------
#         df = pd.read_excel(spec_path)
#         spec = df.set_index("Spec")["Value"].to_dict()

#         is_external = int(spec.get("External", 0))

#         # ------------------------------
#         # Step 1: Get best gm/Id config
#         # ------------------------------
#         if is_external == 1:
#             print("→ Running EXTERNAL gm/Id selection")
#             best_dict = best_gm_id_external(spec_path)
#         else:
#             print("→ Running INTERNAL gm/Id selection")
#             best_dict = best_gm_id_internal(spec_path)

#         if best_dict is None:
#             print("No valid gm/Id found — continuing with default")
#             gm_id_value = 4 / (round(spec["Vin"] - spec["Vout"], 3))
#         else:
#             gm_id_value = best_dict.get("gm_id", None)

#         if gm_id_value is None:
#             print("gm_id missing in returned best config — skipping")
#             continue
#         # print(best_dict)
#         # ------------------------------
#         # Step 2: Run LTSpice simulation
#         # ------------------------------
#         if is_external == 1:
#             print("→ Running EXTERNAL LTspice simulation")
#             sim_dict = run_lt_spice_external(spec_path, gm_id_value)
#         else:
#             print("→ Running INTERNAL LTspice simulation")
#             sim_dict = run_lt_spice_internal(spec_path, gm_id_value)
#         # print(sim_dict)
#         # ------------------------------
#         # Step 3: Combine dictionaries
#         # ------------------------------
#         if best_dict is None:
#             final_dict = sim_dict
#         else:
#             final_dict = {**best_dict, **sim_dict}
#         # ------------------------------
#         # Step 4: Save as CSV
#         # ------------------------------
#         out_file = os.path.join(
#             SPEC_FOLDER, file.replace(".xlsx", "_params.csv")
#         )

#         pd.DataFrame([final_dict]).to_csv(out_file, index=False)

#         print(f"Saved results → {out_file}")
# run_all_specs()
import os
import time
import pandas as pd
import matplotlib.pyplot as plt

from best_gm_id_external import best_gm_id_external
from best_gm_id_internal import best_gm_id_internal
from run_lt_spice_external import run_lt_spice_external
from run_lt_spice_internal import run_lt_spice_internal

SPEC_FOLDER = r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\specs"


def run_all_specs():

    for file in os.listdir(SPEC_FOLDER):

        if not file.endswith(".xlsx"):
            continue

        spec_path = os.path.join(SPEC_FOLDER, file)
        print(f"\n=============================")
        print(f"Processing spec: {file}")
        print(f"=============================")

        df = pd.read_excel(spec_path)
        base_spec = df.set_index("Spec")["Value"].to_dict()
        is_external = int(base_spec.get("External", 0))

        iterations_list = []
        gm_times = []
        spice_times = []
        total_times = []
        iteration_df = pd.DataFrame()

        # ==========================================================
        #  ITERATION SWEEP (1 → 100 STEP 10)
        # ==========================================================
        for iterations in [1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:

            print(f"\n--- Running iteration sweep = {iterations} ---")

            spec = dict(base_spec)
            spec["iterations"] = iterations

            # ------------------------------
            # Step 1: gm/Id timing
            # ------------------------------
            t0 = time.time()

            if is_external == 1:
                best_dict = best_gm_id_external(spec_path)
            else:
                best_dict = best_gm_id_internal(spec_path)

            gm_time = time.time() - t0

            if best_dict is None:
                gm_id_value = 4 / (round(spec["Vin"] - spec["Vout"], 3))
            else:
                gm_id_value = best_dict.get("gm_id", None)

            if gm_id_value is None:
                print("gm_id missing — skipping iteration")
                continue

            # ------------------------------
            # Step 2: LTSpice timing
            # ------------------------------
            t1 = time.time()

            if is_external == 1:
                sim_dict = run_lt_spice_external(spec_path, gm_id_value)
            else:
                sim_dict = run_lt_spice_internal(spec_path, gm_id_value)

            spice_time = time.time() - t1
            if best_dict is None:
                final_dict = sim_dict
                Best_or_default = "Default"
            else:
                final_dict = {**best_dict, **sim_dict}
                Best_or_default = "Best"
            # ------------------------------
            # Step 4: Save as CSV
            # ------------------------------
            final_dict["Best_or_default"] = Best_or_default
            iteration_df = pd.concat([iteration_df, pd.DataFrame([final_dict])], ignore_index=True)
            
            # Collect timing
            iterations_list.append(iterations)
            gm_times.append(gm_time)
            spice_times.append(spice_time)
            total_times.append(gm_time + spice_time)

        # ==========================================================
        #  PLOT RUNTIMES
        # ==========================================================
        out_file = os.path.join(
            SPEC_FOLDER, file.replace(".xlsx", f"_params.csv")
        )
        iteration_df.to_csv(out_file)
        plt.figure(figsize=(8, 5))
        plt.plot(iterations_list, gm_times, marker='o', label='gm/Id Time (s)')
        plt.plot(iterations_list, spice_times, marker='o', label='LTSpice Time (s)')
        plt.plot(iterations_list, total_times, marker='o', label='Total Time (s)', linewidth=2)

        plt.xlabel("Iterations")
        plt.ylabel("Runtime (seconds)")
        plt.title(f"Runtime vs Iterations — {file}")
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.legend()

        # Save figure inside same folder
        plot_path = os.path.join(
            SPEC_FOLDER, file.replace(".xlsx", "_runtime_plot.png")
        )
        plt.savefig(plot_path, dpi=160)
        plt.close()

        print(f"Runtime plot saved → {plot_path}")


run_all_specs()
