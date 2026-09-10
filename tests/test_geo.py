import pytest
from urja_api.services.meter_service import MeterService

def test_haversine_distance_accuracy():
    # Distance between Jaipur Center (26.9124, 75.7873) and Malviya Nagar (26.8528, 75.8130) is ~ 7.1 km
    service = MeterService(None, None)
    dist = service._haversine_distance(26.9124, 75.7873, 26.8528, 75.8130)
    assert 6.5 < dist < 7.5

def test_haversine_same_point():
    service = MeterService(None, None)
    dist = service._haversine_distance(26.9124, 75.7873, 26.9124, 75.7873)
    assert dist == 0.0
