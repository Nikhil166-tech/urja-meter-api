import pytest
from unittest.mock import AsyncMock
from urja_api.services.energy_service import EnergyService

@pytest.mark.asyncio
async def test_energy_anomaly_detection():
    mock_cache = AsyncMock()
    mock_cache.get_meter_energy.return_value = [
        {"timestamp": "24/06/2026 00:00", "kwh": "100.0", "kvah": "105.0", "voltR": "230"},
        {"timestamp": "24/06/2026 00:30", "kwh": "100.5", "kvah": "105.5", "voltR": "190"}, # Voltage Sag
        {"timestamp": "24/06/2026 01:00", "kwh": "115.0", "kvah": "120.0", "voltR": "255"}, # Consumption Spike + Voltage Swell
    ]

    service = EnergyService(mock_cache)
    summary = await service.get_meter_telemetry("J100000")

    assert summary.total_readings == 3
    assert summary.start_kwh == 100.0
    assert summary.end_kwh == 115.0
    assert summary.net_consumption_kwh == 15.0

    anomaly_types = [a.type for a in summary.anomalies]
    assert "voltage_sag" in anomaly_types
    assert "voltage_swell" in anomaly_types
    assert "consumption_spike" in anomaly_types
