import pytest
from urja_api.client.upstream import UrjaUpstreamClient, UrjaPortalClient

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
    assert len(parsed["nameplate"]) == 1
    assert parsed["nameplate"][0]["parameterName"] == "Make"
    assert parsed["nameplate"][0]["parameterValue"] == "HPL"

def test_parse_meter_html_detail():
    client = UrjaUpstreamClient()
    mock_html = """
    <html>
      <head><title>Meter J100000</title></head>
      <body>
        <nav><span>Jaipur Zone 1</span><span>Circle 1</span></nav>
        <dl>
          <div><dt>Serial No</dt><dd>SE33962</dd></div>
          <div><dt>Make</dt><dd>HPL</dd></div>
          <div><dt>Phase Type</dt><dd>single</dd></div>
        </dl>
      </body>
    </html>
    """
    res = client.parse_meter_html_detail(mock_html, "J100000")
    assert res["meterId"] == "J100000"
    assert len(res["nameplate"]) == 3
    names = [x["parameterName"] for x in res["nameplate"]]
    vals = [x["parameterValue"] for x in res["nameplate"]]
    assert "Serial No" in names
    assert "SE33962" in vals
    assert res["hierarchy"].get("Zone") == "Jaipur Zone 1"

def test_urja_portal_client_alias():
    assert UrjaPortalClient is UrjaUpstreamClient

def test_app_compatibility_layer():
    from app.main import app as app_main
    from app.client import UrjaPortalClient as AppPortalClient
    from app.models import MeterDetail
    from app.config import settings as app_settings
    assert app_main is not None
    assert AppPortalClient is UrjaUpstreamClient
    assert MeterDetail is not None
    assert app_settings is not None
