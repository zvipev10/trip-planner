import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('valhalla_service',Path(__file__).resolve().parents[2]/'valhalla/server.py')
service=importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def test_graph_integrity_is_required(tmp_path,monkeypatch):
    monkeypatch.setattr(service,'version',lambda _: '3.9.1')
    graph=tmp_path/'test.gph';graph.write_bytes(b'graph')
    manifest={'files':{'test.gph':{'bytes':5,'sha256':hashlib.sha256(b'graph').hexdigest()}}}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    assert service.verify_data(tmp_path)==manifest
    graph.write_bytes(b'wrong')
    with pytest.raises(ValueError,match='checksum'):service.verify_data(tmp_path)
    monkeypatch.setattr(service,'version',lambda _: 'different')
    with pytest.raises(ValueError,match='3.9.1'):service.verify_data(tmp_path)


def test_local_service_preserves_22_point_capacity_and_rejects_extra():
    body={'locations':[{'lat':32,'lon':35}]*22,'costing':'auto'}
    assert service.validate_request('route',body) is body
    with pytest.raises(ValueError):service.validate_request('route',{**body,'locations':body['locations']+[{}]})
    with pytest.raises(ValueError):service.validate_request('route',{**body,'costing':'truck'})
    assert service.validate_request('sources_to_targets',{'sources':body['locations'],'targets':body['locations']})
