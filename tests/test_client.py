import pytest
from urja_api.client.upstream import UrjaUpstreamClient

def test_export_signature_generation():
    client = UrjaUpstreamClient()
    secret = "test_signing_secret_12345"
    query = "page=1"
    timestamp = "1725969600"
    
    sig = client.compute_export_signature(query, timestamp, secret)
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex string length
    
    # Deterministic output verification
    sig2 = client.compute_export_signature(query, timestamp, secret)
    assert sig == sig2

def test_parse_sveltekit_meter_data():
    client = UrjaUpstreamClient()
    
    # Mock legacy sveltekit payload
    legacy_payload = {
        "nodes": [
            None,
            {"data": [{"user": 1}, "Operator"], "uses": {}},
            {
                "data": [
                    {"meterId": 1, "detail": 2, "hierarchy": 5},
                    "J100000",
                    {"data": 3},
                    [4],
                    {"parameterName": "Make", "parameterValue": "HPL"},
                    {"Zone": "Jaipur Zone 1"}
                ]
            }
        ]
    }
    
    parsed = client._parse_sveltekit_meter_data(legacy_payload, "J100000")
    assert parsed["meterId"] == "J100000"
