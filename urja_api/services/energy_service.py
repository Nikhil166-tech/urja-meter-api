import logging
from typing import Any, Dict, List, Optional

from urja_api.client.exceptions import UpstreamNotFoundError
from urja_api.models.energy import (
    EnergyAnomaly,
    EnergyConsumptionSummary,
    EnergyReading,
)
from urja_api.services.cache_service import LocalDataCache

logger = logging.getLogger(__name__)

class EnergyService:
    """Processes interval telemetry readings and identifies grid anomalies."""

    def __init__(self, cache: LocalDataCache):
        self.cache = cache

    async def get_meter_telemetry(self, meter_id: str, force_refresh: bool = False) -> EnergyConsumptionSummary:
        raw_readings = await self.cache.get_meter_energy(meter_id, force_refresh=force_refresh)
        
        parsed_readings: List[EnergyReading] = []
        voltages: List[float] = []
        anomalies: List[EnergyAnomaly] = []

        prev_kwh: Optional[float] = None
        prev_kvah: Optional[float] = None

        for r in raw_readings:
            ts = r.get("timestamp", "")
            
            kwh_val = float(r["kwh"]) if r.get("kwh") and r["kwh"] != "—" else None
            kvah_val = float(r["kvah"]) if r.get("kvah") and r["kvah"] != "—" else None
            v_val = float(r["voltR"]) if r.get("voltR") and r["voltR"] != "—" else None

            # Calculate instantaneous power factor if interval diffs available
            pf = None
            if kwh_val is not None and kvah_val is not None and prev_kwh is not None and prev_kvah is not None:
                delta_kwh = max(0.0, kwh_val - prev_kwh)
                delta_kvah = max(0.0, kvah_val - prev_kvah)
                if delta_kvah > 0.001:
                    pf = min(1.0, max(0.0, round(delta_kwh / delta_kvah, 3)))
                
                # Check for consumption spike (e.g. delta_kwh > 10 kWh in 30 mins for LT meter)
                if delta_kwh > 10.0:
                    anomalies.append(EnergyAnomaly(
                        type="consumption_spike",
                        severity="medium",
                        timestamp=ts,
                        description=f"Rapid energy consumption jump of {delta_kwh:.2f} kWh in 30 min interval",
                        observed_value=delta_kwh,
                        threshold_value=10.0,
                    ))

            if v_val is not None:
                voltages.append(v_val)
                # Voltage sag (< 210V nominal single-phase is 230V ±6%)
                if v_val < 205.0:
                    anomalies.append(EnergyAnomaly(
                        type="voltage_sag",
                        severity="high" if v_val < 195.0 else "medium",
                        timestamp=ts,
                        description=f"Voltage sag detected at {v_val}V (Nominal: 230V)",
                        observed_value=v_val,
                        threshold_value=205.0,
                    ))
                # Voltage swell (> 250V)
                elif v_val > 250.0:
                    anomalies.append(EnergyAnomaly(
                        type="voltage_swell",
                        severity="high" if v_val > 260.0 else "medium",
                        timestamp=ts,
                        description=f"Voltage swell detected at {v_val}V (Nominal: 230V)",
                        observed_value=v_val,
                        threshold_value=250.0,
                    ))

            if kwh_val is not None:
                prev_kwh = kwh_val
            if kvah_val is not None:
                prev_kvah = kvah_val

            parsed_readings.append(EnergyReading(
                timestamp=ts,
                kwh=kwh_val,
                kvah=kvah_val,
                voltage_r=v_val,
                power_factor=pf,
            ))

        total_readings = len(parsed_readings)
        earliest_ts = parsed_readings[0].timestamp if total_readings > 0 else None
        latest_ts = parsed_readings[-1].timestamp if total_readings > 0 else None

        valid_kwhs = [r.kwh for r in parsed_readings if r.kwh is not None]
        start_kwh = valid_kwhs[0] if valid_kwhs else None
        end_kwh = valid_kwhs[-1] if valid_kwhs else None
        net_kwh = round(end_kwh - start_kwh, 2) if (start_kwh is not None and end_kwh is not None) else None

        avg_v = round(sum(voltages) / len(voltages), 1) if voltages else None
        min_v = min(voltages) if voltages else None
        max_v = max(voltages) if voltages else None

        valid_pfs = [r.power_factor for r in parsed_readings if r.power_factor is not None]
        avg_pf = round(sum(valid_pfs) / len(valid_pfs), 2) if valid_pfs else None

        return EnergyConsumptionSummary(
            meter_id=meter_id,
            total_readings=total_readings,
            earliest_reading=earliest_ts,
            latest_reading=latest_ts,
            start_kwh=start_kwh,
            end_kwh=end_kwh,
            net_consumption_kwh=net_kwh,
            avg_voltage=avg_v,
            min_voltage=min_v,
            max_voltage=max_v,
            avg_power_factor=avg_pf,
            anomalies=anomalies,
            readings=parsed_readings,
        )
