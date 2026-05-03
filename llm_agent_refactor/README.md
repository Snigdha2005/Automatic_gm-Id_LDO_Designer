# LDO Automation – Refactored Architecture

## Overview

```
ldo_automation/
├── main.py                  ← Entry point (interactive + batch modes)
├── llm_agent.py             ← Claude-powered agent: spec parsing, topology,
│                               relaxation suggestions
├── transistor.py            ← Transistor base class + PMOS / NMOS subclasses
├── best_gm_id_internal.py   ← gm/Id sweep for internally-compensated LDO
├── best_gm_id_external.py   ← gm/Id sweep for externally-compensated LDO
│                               (port the same pattern as internal)
├── run_lt_spice_internal.py ← LTSpice run + post-processing (internal)
├── run_lt_spice_external.py ← LTSpice run + post-processing (external)
└── _sim_utils.py            ← Shared: modify_cir_params, run_ltspice_cir,
                                all_in_saturation, analyze_loopgain, plot_trends
```

---

## What Changed

### 1. `transistor.py` — New

| Class | Role |
|-------|------|
| `Transistor` (ABC) | Loads techplot CSVs lazily; provides `gmro_at`, `idw_at`, `ft_at`, `available_lengths`, abstract `size()` |
| `PMOS(Transistor)` | Implements `size()` + `size_pass_device()` (handles light-load gm, Cgg/Cgd, wp2) |
| `NMOS(Transistor)` | Implements `size()` with auto-length selection based on gmro requirement |

**Design methodology is unchanged** – all formulas, interpolation logic, and
length-selection loops are identical to the original; they are simply
encapsulated in class methods.

### 2. `llm_agent.py` — New

| Function | Purpose |
|----------|---------|
| `parse_input(text)` | Accepts free-text OR JSON spec; calls Claude to extract spec + topology |
| `validate_spec(spec)` | Physical sanity check (dropout, current ratios, Cload range) |
| `suggest_relaxations(spec, reason)` | Returns 3 targeted relaxation suggestions when no design is found |
| `format_relaxation_prompt(info)` | Formats suggestions as "reduce PSRR from 60 dB → 55 dB?" |
| `apply_relaxation(spec, info, choice)` | Applies the chosen relaxation to the spec dict |

### 3. `_sim_utils.py` — New (extracted, not changed)

Shared simulation utilities formerly duplicated in both `best_gm_id_internal`
and `best_gm_id_external`.  Logic is **identical** to the original.

### 4. `best_gm_id_internal.py` — Refactored

- `PMOS`/`NMOS` objects created once before the sweep loop.
- Pass-FET sizing delegated to `pmos_dev.size_pass_device(...)`.
- OTA diff-pair sizing delegated to `nmos_dev.size(..., gmro_required=...)`.
- OTA load sizing delegated to `pmos_dev.size(..., gmro_required=...)`.
- All other calculations (Cc, LTSpice call, error metrics) unchanged.

### 5. `main.py` — New

Two modes:

```bash
# Interactive (AI-assisted):
python main.py

# Batch (process all .xlsx files in SPEC_FOLDER):
python main.py --batch
```

**Interactive mode flow:**

```
User types application description
        ↓
LLM agent → topology + spec dict
        ↓
Spec validation
        ↓
run_with_relaxation()
   └─ run_design() [gm/Id sweep + LTSpice]
        ↓ (if no valid design)
   LLM suggests relaxations ("reduce PSRR 60→55 dB?")
   User chooses → spec updated
        ↓ (repeat up to 5 rounds)
   Best design printed + saved as CSV
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TECHPLOT_PATH` | `C:\Users\...\Techplots_180nm_2024` | Root folder for techplot CSVs |
| `ASC_FILE_INTERNAL` | `...\LDO_loopgain_IIIT.cir` | Internal LDO netlist |
| `LTSPICE_PATH` | `C:\Program Files\LTC\LTspiceXVII\XVIIx64.exe` | LTSpice executable |
| `SPEC_FOLDER` | `C:\Users\...\specs` | Folder for Excel spec files |

---

## Topology Selection Logic (LLM-guided)

| Condition | Topology |
|-----------|----------|
| Cload > 1 µF OR Iload > 50 mA | External |
| On-chip, Cload < 1 µF, Iq < 500 µA | Internal |
| IoT / wearable / area-constrained | Internal |
| Board-level cap mandatory | External |

---

## Extending to External Compensation

Port `best_gm_id_external.py` using the same pattern as internal:
1. Create `PMOS(BASE_PATH_EXT, vds)` and `NMOS(...)` objects.
2. Call `pmos_dev.size_pass_device(...)` for pass FET.
3. Call `nmos_dev.size(...)` and `pmos_dev.size(...)` for OTA stages.
4. Import shared utilities from `_sim_utils`.
