"""
transistor.py
=============
Base Transistor class and PMOS / NMOS subclasses.
Each subclass knows how to:
  - load its own techplot CSVs
  - size itself given a gm/Id target and a bias current
  - report gm, ro, W for a chosen channel length
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_filename(base_path: str, device: str, vds: float, n_or_p: str,
                    plot_type: str, W: int = 5000) -> str:
    """Construct a techplot CSV filename from naming convention."""
    vds_str = str(vds).replace(".", "p")
    filename = f"{device}{n_or_p}{plot_type}_VDS_{vds_str}V_W_{W}um.csv"
    return os.path.join(base_path, filename)


def _interp(x_vals: np.ndarray, y_vals: np.ndarray,
            query: float) -> float:
    """1-D linear interpolation with extrapolation."""
    fn = interp1d(x_vals, y_vals, fill_value="extrapolate")
    return float(fn(query))


def _find_col(df: pd.DataFrame, length_um: float, suffix: str) -> str:
    """Return the column name for a given length and suffix (_X or _Y)."""
    key = f"L___{int(length_um * 1e3)}nm{suffix}"
    if key not in df.columns:
        raise KeyError(f"Column '{key}' not found in DataFrame. "
                       f"Available: {list(df.columns)}")
    return key


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class Transistor(ABC):
    """
    Abstract base class for a MOSFET device.

    Parameters
    ----------
    base_path : str
        Root folder containing all techplot CSV files.
    vds : float
        |Vds| bias point used to select the correct CSV files (e.g. 0.4).
    """

    #: Override in subclasses – used to build CSV file names
    _device_prefix: str = ""
    _polarity_char: str = ""       # 'N' or 'P'

    #: Column name for the single-length table (L = 180 nm)
    L_COL = "L___180nm"

    def __init__(self, base_path: str, vds: float) -> None:
        self.base_path = base_path
        self.vds = vds

        # DataFrames loaded lazily
        self._gmro_df: Optional[pd.DataFrame] = None
        self._idw_df:  Optional[pd.DataFrame] = None
        self._ft_df:   Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _csv_path(self, plot_type: str) -> str:
        return _build_filename(
            self.base_path,
            self._device_prefix,
            self.vds,
            self._polarity_char,
            plot_type,
        )

    def _load_gmro(self) -> pd.DataFrame:
        if self._gmro_df is None:
            self._gmro_df = pd.read_csv(self._csv_path("GMRo"))
        return self._gmro_df

    def _load_idw(self) -> pd.DataFrame:
        if self._idw_df is None:
            self._idw_df = pd.read_csv(self._csv_path("IDW"))
        return self._idw_df

    def _load_ft(self) -> pd.DataFrame:
        if self._ft_df is None:
            self._ft_df = pd.read_csv(self._csv_path("FT"))
        return self._ft_df

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def available_lengths(self) -> list[float]:
        """
        Return sorted list of channel lengths [µm] available in the
        multi-length gmro table.
        """
        df = self._load_gmro()
        lengths = [
            float(col.replace("L___", "").replace("nm_X", "")) / 1e3
            for col in df.columns
            if "_X" in col
        ]
        return sorted(lengths)

    def gmro_at(self, gm_id: float, length_um: float) -> float:
        """Return gmro for a given gm/Id and channel length [µm]."""
        df = self._load_gmro()
        x_col = _find_col(df, length_um, "_X")
        y_col = _find_col(df, length_um, "_Y")
        return _interp(df[x_col].values, df[y_col].values, gm_id)

    def idw_at(self, gm_id: float, length_um: float) -> float:
        """Return Id/W [mA/µm] for a given gm/Id and channel length [µm]."""
        df = self._load_idw()
        x_col = _find_col(df, length_um, "_X")
        y_col = _find_col(df, length_um, "_Y")
        return _interp(df[x_col].values, df[y_col].values, gm_id)

    def ft_at(self, gm_id: float) -> float:
        """
        Return fT [Hz] for a given gm/Id using the single-length (180 nm) table.
        """
        df = self._load_ft()
        x_vals = df[f"{self.L_COL}_X"].values
        y_vals = df[f"{self.L_COL}_Y"].values
        return _interp(x_vals, y_vals, gm_id)

    @abstractmethod
    def size(self, gm_id: float, Id_uA: float,
             gmro_required: Optional[float] = None,
             length_um: Optional[float] = None) -> dict:
        """
        Size the transistor.

        Parameters
        ----------
        gm_id : float
            Target gm/Id ratio.
        Id_uA : float
            Drain current in µA.
        gmro_required : float, optional
            Minimum gmro that must be satisfied; used to auto-select length.
        length_um : float, optional
            If provided, skip length search and use this value directly.

        Returns
        -------
        dict with keys: W, gm, ro, gmro, chosen_L, idw
        """


# ---------------------------------------------------------------------------
# PMOS subclass
# ---------------------------------------------------------------------------

class PMOS(Transistor):
    """PMOS transistor – uses 'P' techplot files."""

    _device_prefix = "P"
    _polarity_char = "P"

    def size(self, gm_id: float, Id_uA: float,
             gmro_required: Optional[float] = None,
             length_um: Optional[float] = None) -> dict:
        """
        Size a PMOS device.

        Uses the L=180 nm techplot by default unless *gmro_required* or
        *length_um* forces a specific length.
        """
        chosen_L = length_um

        # ---- auto-select shortest L that satisfies gmro_required ----------
        if chosen_L is None and gmro_required is not None:
            for L in self.available_lengths():
                if self.gmro_at(gm_id, L) >= gmro_required:
                    chosen_L = L
                    break
            if chosen_L is None:
                return {}   # no length satisfies requirement

        # ---- fallback: use 180 nm -----------------------------------------
        if chosen_L is None:
            chosen_L = 0.18

        gmro  = self.gmro_at(gm_id, chosen_L)
        idw   = self.idw_at(gm_id, chosen_L)
        gm    = gm_id * Id_uA / 1e6          # [A/V]
        ro    = gmro / gm                     # [Ω]
        W     = Id_uA / (idw * 1e3)          # idw is mA/µm → W in µm

        return {
            "W":        W,
            "gm":       gm,
            "ro":       ro,
            "gmro":     gmro,
            "chosen_L": chosen_L,
            "idw":      idw,
        }

    def size_pass_device(self, gm_id: float, Iload_mA: float,
                         Iload_light_mA: float,
                         cload_uF: float) -> dict:
        """
        Full pass-FET sizing including light-load gm and parasitic Cgg/Cgd.

        Parameters
        ----------
        gm_id       : gm/Id target
        Iload_mA    : maximum (heavy) load current [mA]
        Iload_light_mA : minimum (light) load current [mA]
        cload_uF    : external load capacitor [µF]

        Returns
        -------
        dict with all pass-FET parameters needed by the design engine.
        """
        # ---------- heavy-load sizing --------------------------------------
        result = self.size(gm_id, Iload_mA * 1e3)   # Id_uA = Iload_mA*1000
        if not result:
            return {}

        W     = result["W"]
        gm    = result["gm"]
        ro    = result["ro"]
        gmro  = result["gmro"]
        chosen_L = result["chosen_L"]

        # fT → Cgg, Cgd (single-L table)
        ft       = self.ft_at(gm_id)
        cgs_cgd  = gm * 1e6 / (2 * np.pi * ft)      # [µF]
        cgd      = 0.33 * cgs_cgd

        # ---------- light-load sizing (for fp2 at light load) --------------
        idw_vals_180nm = self._load_idw()[f"{self.L_COL}_Y"].values
        gm_id_vals_180nm = self._load_idw()[f"{self.L_COL}_X"].values
        id_w_light   = Iload_light_mA * 1e3 / W      # mA/µm at light load
        gm_id_from_idw = interp1d(idw_vals_180nm, gm_id_vals_180nm,
                                   fill_value="extrapolate")
        gm_id_light   = float(gm_id_from_idw(id_w_light))
        gm_ro_light   = self.gmro_at(gm_id_light, chosen_L)
        gm_light      = gm_id_light * Iload_light_mA * 1e3 / 1e6

        # ---------- poles --------------------------------------------------
        wp2_heavy = gm * 1e6 / (cload_uF + cgs_cgd / 2)
        wp2_light = gm_light * 1e6 / cload_uF
        fp2_light = wp2_light / (2 * np.pi)

        return {
            "W":          W,
            "gm":         gm,
            "gm_light":   gm_light,
            "ro":         ro,
            "gmro":       gmro,
            "chosen_L":   chosen_L,
            "cgs_cgd":    cgs_cgd,
            "cgd":        cgd,
            "wp2_heavy":  wp2_heavy,
            "wp2_light":  wp2_light,
            "fp2_light":  fp2_light,
            "gm_ro_light": gm_ro_light,
        }


# ---------------------------------------------------------------------------
# NMOS subclass
# ---------------------------------------------------------------------------

class NMOS(Transistor):
    """NMOS transistor – uses 'N' techplot files."""

    _device_prefix = "N"
    _polarity_char = "N"

    def size(self, gm_id: float, Id_uA: float,
             gmro_required: Optional[float] = None,
             length_um: Optional[float] = None) -> dict:
        """
        Size an NMOS device.

        Automatically finds the shortest channel length that satisfies
        *gmro_required* when provided.
        """
        chosen_L = length_um

        # ---- auto-select shortest L that satisfies gmro_required ----------
        if chosen_L is None and gmro_required is not None:
            for L in self.available_lengths():
                gmro_at_L = self.gmro_at(gm_id, L)
                if gmro_at_L >= gmro_required:
                    chosen_L = L
                    break
            if chosen_L is None:
                return {}   # no length satisfies requirement

        # ---- fallback: use 180 nm -----------------------------------------
        if chosen_L is None:
            chosen_L = 0.18

        gmro  = self.gmro_at(gm_id, chosen_L)
        idw   = self.idw_at(gm_id, chosen_L)
        gm    = gm_id * Id_uA / 1e6          # [A/V]
        ro    = gmro / gm                     # [Ω]
        W     = Id_uA / (idw * 1e3)          # [µm]

        return {
            "W":        W,
            "gm":       gm,
            "ro":       ro,
            "gmro":     gmro,
            "chosen_L": chosen_L,
            "idw":      idw,
        }
