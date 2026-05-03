"""
main.py
=======
Top-level orchestrator for the LDO automation flow.

Usage
-----
    python main.py

The script will:
  1. Ask the user for an application description OR a spec dict (text input).
  2. Use the LLM agent to parse the input, select topology, and extract a spec.
  3. Validate the spec for physical plausibility.
  4. Run the gm/Id sweep + LTSpice simulations.
  5. If no valid design is found, suggest targeted spec relaxations and
     allow the user to iteratively relax until a solution is found.
  6. Save results as CSV and runtime plots.
"""

from __future__ import annotations

import os
import sys
import time

import pandas as pd
import matplotlib.pyplot as plt

import llm_agent as agent

# ---------------------------------------------------------------------------
# Dynamic import – choose internal or external flow at runtime
# ---------------------------------------------------------------------------

def _import_flow(is_external: int):
    if is_external:
        from best_gm_id_external import best_gm_id_external as _best
        from run_lt_spice_external import run_lt_spice_external as _run
    else:
        from best_gm_id_internal import best_gm_id_internal as _best
        from run_lt_spice_internal import run_lt_spice_internal as _run
    return _best, _run


SPEC_FOLDER = os.environ.get(
    "SPEC_FOLDER",
    r"C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\specs",
)

# Maximum number of relaxation rounds before giving up
MAX_RELAX_ROUNDS = 5


# ---------------------------------------------------------------------------
# Spec ↔ Excel helpers
# ---------------------------------------------------------------------------

def _spec_to_excel(spec: dict, path: str) -> None:
    """Write a spec dict to a two-column Excel file (Spec / Value)."""
    rows = [{"Spec": k, "Value": v} for k, v in spec.items()]
    pd.DataFrame(rows).to_excel(path, index=False)


def _excel_to_spec(path: str) -> dict:
    df = pd.read_excel(path)
    return df.set_index("Spec")["Value"].to_dict()


# ---------------------------------------------------------------------------
# Core design runner (single spec, full iteration sweep)
# ---------------------------------------------------------------------------

def run_design(spec: dict, spec_path: str, label: str = "design") -> dict | None:
    """
    Run the full gm/Id sweep and LTSpice simulations for one spec.

    Returns the best parameter dict, or None if no valid point was found.
    Also saves a runtime plot and a CSV of all iteration results.
    """
    is_external = int(spec.get("External", 0))
    best_fn, run_fn = _import_flow(is_external)

    iterations_list, gm_times, spice_times, total_times = [], [], [], []
    iteration_df = pd.DataFrame()

    sweep_points = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    for iterations in sweep_points:
        print(f"\n--- Iteration sweep = {iterations} ---")

        working_spec = {**spec, "iterations": iterations}
        _spec_to_excel(working_spec, spec_path)

        # ---- gm/Id timing ------------------------------------------------
        t0 = time.time()
        best_dict = best_fn(spec_path)
        gm_time   = time.time() - t0

        if best_dict is None:
            gm_id_value = 4 / round(spec["Vin"] - spec["Vout"], 3)
            best_or_default = "Default"
        else:
            gm_id_value     = best_dict.get("gm_id")
            best_or_default = "Best"

        if gm_id_value is None:
            print("  gm_id missing in best config – skipping")
            continue

        # ---- LTSpice timing ----------------------------------------------
        t1 = time.time()
        sim_dict  = run_fn(spec_path, gm_id_value)
        spice_time = time.time() - t1

        final_dict = {**(best_dict or {}), **sim_dict,
                      "Best_or_default": best_or_default}

        iteration_df = pd.concat(
            [iteration_df, pd.DataFrame([final_dict])], ignore_index=True
        )

        iterations_list.append(iterations)
        gm_times.append(gm_time)
        spice_times.append(spice_time)
        total_times.append(gm_time + spice_time)

    # ---- Save CSV --------------------------------------------------------
    out_csv = spec_path.replace(".xlsx", f"_{label}_params.csv")
    iteration_df.to_csv(out_csv, index=False)
    print(f"Results saved → {out_csv}")

    # ---- Runtime plot ----------------------------------------------------
    if iterations_list:
        plt.figure(figsize=(8, 5))
        plt.plot(iterations_list, gm_times,    marker="o", label="gm/Id Time (s)")
        plt.plot(iterations_list, spice_times, marker="o", label="LTSpice Time (s)")
        plt.plot(iterations_list, total_times, marker="o",
                 label="Total Time (s)", linewidth=2)
        plt.xlabel("Iterations")
        plt.ylabel("Runtime (seconds)")
        plt.title(f"Runtime vs Iterations — {label}")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.legend()
        plot_path = spec_path.replace(".xlsx", f"_{label}_runtime.png")
        plt.savefig(plot_path, dpi=160)
        plt.close()
        print(f"Runtime plot saved → {plot_path}")

    # Return the last known best_dict (from the 100-iteration run if available)
    return best_dict


# ---------------------------------------------------------------------------
# Interactive relaxation loop
# ---------------------------------------------------------------------------

def run_with_relaxation(spec: dict, spec_path: str, label: str = "design") -> dict | None:
    """
    Attempt to find a valid design.  If no valid point is found after the
    initial run, ask the user (via LLM-generated suggestions) to relax the
    spec and try again, up to MAX_RELAX_ROUNDS times.
    """
    current_spec = dict(spec)

    for round_idx in range(MAX_RELAX_ROUNDS + 1):
        if round_idx == 0:
            print("\n🚀  Starting design run...")
        else:
            print(f"\n🔄  Design run (after relaxation #{round_idx})...")

        best = run_design(current_spec, spec_path, label=f"{label}_r{round_idx}")

        if best is not None:
            print("\n✅  Valid design found!")
            return best

        # No valid design – decide failure reason heuristically
        dropout = current_spec["Vin"] - current_spec["Vout"]
        failure_reason = (
            "No gm/Id operating point satisfied all constraints: "
            "phase margin ≥ 45°, Cc > 0, and all devices in saturation. "
            f"Dropout = {dropout:.3f} V, PSRR target = {current_spec['PSRR']} dB, "
            f"Iload_max = {current_spec['Iload|max']} mA."
        )

        # Ask LLM for relaxation suggestions
        relaxation_info = agent.suggest_relaxations(current_spec, failure_reason)
        prompt_text     = agent.format_relaxation_prompt(relaxation_info)
        print(prompt_text)

        user_choice = input("Your choice: ").strip().lower()
        if user_choice == "skip" or user_choice == "":
            print("Aborting – no valid design found.")
            return None

        try:
            choice = int(user_choice)
            current_spec = agent.apply_relaxation(
                current_spec, relaxation_info, choice
            )
            # Update External flag to match topology
            current_spec["External"] = (
                1 if current_spec.get("External", 0) else 0
            )
        except (ValueError, IndexError) as exc:
            print(f"Invalid choice: {exc}. Aborting.")
            return None

    print(f"Maximum relaxation rounds ({MAX_RELAX_ROUNDS}) reached. Aborting.")
    return None


# ---------------------------------------------------------------------------
# Batch runner (existing spec Excel files)
# ---------------------------------------------------------------------------

def run_all_specs() -> None:
    """Process every .xlsx file in SPEC_FOLDER (original batch behaviour)."""
    for file in os.listdir(SPEC_FOLDER):
        if not file.endswith(".xlsx"):
            continue

        spec_path = os.path.join(SPEC_FOLDER, file)
        print(f"\n{'='*50}")
        print(f"Processing spec: {file}")
        print(f"{'='*50}")

        spec = _excel_to_spec(spec_path)
        run_with_relaxation(spec, spec_path, label=os.path.splitext(file)[0])


# ---------------------------------------------------------------------------
# Interactive single-shot mode (LLM agent)
# ---------------------------------------------------------------------------

def run_interactive() -> None:
    """
    Interactive mode: accept free-text application description or a spec
    dict, run the LLM agent, then execute the design flow.
    """
    print("=" * 60)
    print("  LDO Automation – AI-Assisted Design Entry")
    print("=" * 60)
    print(
        "\nDescribe your application or paste a spec dictionary.\n"
        "Example: 'IoT sensor hub, 1.8 V output from 3.3 V rail, "
        "max 10 mA load, PSRR > 55 dB, low quiescent current'\n"
    )

    lines = []
    print("Input (press Enter twice when done):")
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    user_input = "\n".join(lines).strip()

    if not user_input:
        print("No input provided. Exiting.")
        return

    # ---- Parse input via LLM agent ---------------------------------------
    print("\n⏳  Analysing input with LLM agent...")
    try:
        parsed = agent.parse_input(user_input)
    except Exception as exc:
        print(f"❌  LLM agent error: {exc}")
        return

    topology = parsed["topology"]
    spec     = parsed["spec"]

    print(f"\n📐  Topology selected: {topology.upper()}")
    print(f"    {parsed.get('justification', '')}")
    print("\n📋  Extracted specification:")
    for k, v in spec.items():
        print(f"    {k:20s}: {v}")

    # ---- Validate spec ---------------------------------------------------
    validation = agent.validate_spec(spec)
    if not validation["valid"]:
        print("\n⚠️  Spec validation issues detected:")
        for issue in validation["issues"]:
            print(f"   • {issue}")
        cont = input("\nContinue anyway? [y/N]: ").strip().lower()
        if cont != "y":
            print("Exiting.")
            return

    # ---- Write spec to a temporary Excel file ----------------------------
    os.makedirs(SPEC_FOLDER, exist_ok=True)
    spec_path = os.path.join(SPEC_FOLDER, "interactive_spec.xlsx")
    _spec_to_excel(spec, spec_path)
    print(f"\n💾  Spec saved to: {spec_path}")

    # ---- Run design with automatic relaxation loop -----------------------
    best = run_with_relaxation(spec, spec_path, label="interactive")
    if best:
        print("\n🏆  Best design parameters:")
        for k, v in best.items():
            print(f"    {k:20s}: {v}")
    else:
        print("\n❌  Could not find a valid design.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        run_all_specs()
    else:
        run_interactive()
