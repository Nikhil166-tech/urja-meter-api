from typing import List, Optional
from pydantic import BaseModel, Field

class EnergyReading(BaseModel):
    """Single 30-minute interval smart meter telemetry reading."""
    timestamp: str = Field(..., description="Reading timestamp in 'DD/MM/YYYY HH:MM' format", examples=["24/06/2026 00:00"])
    kwh: Optional[float] = Field(None, description="Active energy in kWh", examples=[48439.16])
    kvah: Optional[float] = Field(None, description="Apparent energy in kVAh", examples=[52314.29])
    voltage_r: Optional[float] = Field(None, description="R-Phase voltage in Volts", examples=[229.0])
    power_factor: Optional[float] = Field(None, description="Calculated power factor (kWh/kVAh incremental ratio)")

class EnergyAnomaly(BaseModel):
    """Detected anomaly or alert from meter telemetry."""
    type: str = Field(..., description="Anomaly classification: voltage_sag, voltage_swell, power_factor_drop, consumption_spike")
    severity: str = Field(..., description="Severity level: low, medium, high, critical")
    timestamp: str = Field(..., description="Timestamp of the incident")
    description: str = Field(..., description="Detailed description of the anomaly")
    observed_value: float = Field(..., description="Metric value observed")
    threshold_value: float = Field(..., description="Expected normal threshold")

class EnergyConsumptionSummary(BaseModel):
    """Telemetry consumption statistics and anomaly assessment."""
    meter_id: str = Field(..., description="Meter ID")
    total_readings: int = Field(..., description="Number of interval readings in window")
    earliest_reading: Optional[str] = Field(None, description="Window start timestamp")
    latest_reading: Optional[str] = Field(None, description="Window end timestamp")
    start_kwh: Optional[float] = Field(None, description="Initial cumulative kWh reading")
    end_kwh: Optional[float] = Field(None, description="Final cumulative kWh reading")
    net_consumption_kwh: Optional[float] = Field(None, description="Net active energy consumed in window")
    avg_voltage: Optional[float] = Field(None, description="Average R-phase voltage (V)")
    min_voltage: Optional[float] = Field(None, description="Minimum recorded voltage (V)")
    max_voltage: Optional[float] = Field(None, description="Maximum recorded voltage (V)")
    avg_power_factor: Optional[float] = Field(None, description="Average estimated power factor")
    anomalies: List[EnergyAnomaly] = Field(default_factory=list, description="Identified telemetry anomalies")
    readings: List[EnergyReading] = Field(default_factory=list, description="Chronological interval readings")
