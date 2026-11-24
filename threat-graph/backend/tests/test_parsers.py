import json

from app.ingestion.parsers import extract_iocs, parse_content, valid_domain, valid_hash, valid_ip


def test_extract_iocs():
    text = (
        "See 192.0.2.41 and https://secure-verify.example/path with hash 275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"
    )
    iocs = extract_iocs(text)
    assert iocs["ip"] == ["192.0.2.41"]
    assert iocs["domain"] == ["secure-verify.example"]
    assert len(iocs["hash"]) == 1
    assert iocs["url"] == ["https://secure-verify.example/path"]


def test_validation_helpers():
    assert valid_ip("203.0.113.19")
    assert not valid_ip("999.1.1.1")
    assert valid_domain("cdn-update.example")
    assert not valid_domain("bad_domain")
    assert valid_hash("d41d8cd98f00b204e9800998ecf8427e")
    assert not valid_hash("not-a-hash")


def test_stix_bundle_parsing():
    bundle = {
        "type": "bundle",
        "objects": [
            {
                "type": "indicator",
                "id": "indicator--1",
                "pattern": "[ipv4-addr:value = '192.0.2.41']",
                "labels": ["malicious-activity"],
                "confidence": 90,
            }
        ],
    }
    result = parse_content(json.dumps(bundle).encode(), "intel.json")
    assert result.format == "stix"
    assert len(result.indicators) == 1
    assert result.indicators[0]["value"] == "192.0.2.41"
    assert result.indicators[0]["severity"].value == "high"
