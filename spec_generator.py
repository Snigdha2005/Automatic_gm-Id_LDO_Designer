import numpy as np
import pandas as pd

np.random.seed(42)

N = 7000
VDROPS = np.array([0.2, 0.4, 1.8])

rows = []

while len(rows) < N:
    # Choose LDO type
    ldo_type = np.random.choice(["External", "Internal"])

    # Output voltage
    Vout = np.random.uniform(0.9, 1.2)

    # Discrete dropout constraint
    Vdrop = np.random.choice(VDROPS)
    Vin = Vout + Vdrop

    # External vs Internal specs
    if ldo_type == "External":
        PSRR = np.random.uniform(50, 70)              # dB
        Iload_max = np.random.uniform(5, 100)         # mA
        Iload_min = np.random.uniform(1, 5)           # mA
        Cload = np.random.uniform(0.1, 5.0)           # uF
    else:
        PSRR = np.random.uniform(30, 50)              # dB
        Iload_max = np.random.uniform(5, 50)           # mA
        Iload_min = np.random.uniform(1, 10)           # mA
        Cload = np.random.uniform(0.001, 0.01)         # uF

    # Quiescent current (must be much smaller than load)
    Iq = np.random.uniform(10, 100)                    # uA

    # Transient duration
    transient_duration = np.random.choice([0.5, 1.0, 2.0])  # us

    # Physical validity checks
    if Iload_min >= Iload_max:
        continue
    if Iq > 0.01 * Iload_max * 1e3:  # Iq << Iload (convert mA → uA)
        continue

    rows.append([
        Vin,
        Vout,
        PSRR,
        Iload_max,
        Iload_min,
        Cload,
        Iq,
        transient_duration,
        ldo_type
    ])

# Create DataFrame
df = pd.DataFrame(rows, columns=[
    "Vin",
    "Vout",
    "PSRR",
    "Iload|max",
    "Iload|min",
    "Cload",
    "Iquiescent",
    "Transient Duration",
    "LDO Type"
])

print(df.head())
print("\nTotal rows:", len(df))

df.to_csv("ldo_specs_5500.csv", index=False)
