"""Bounded read-only check of August-issued A/D orbit catalogue entries."""
import json
import requests
import xml.etree.ElementTree as ET
from pathlib import Path

root=Path("artifacts/p01-implementation-2026-09-06")
session=requests.Session()
session.trust_env=False
out=[]
for satellite in ("S1A","S1D"):
    response=session.get("https://s1-orbits.s3.amazonaws.com",
        params={"list-type":"2","prefix":f"AUX_POEORB/{satellite}_OPER_AUX_POEORB_OPOD_202608","max-keys":"1"},
        timeout=(10,20))
    response.raise_for_status()
    key=ET.fromstring(response.content).findtext("{*}Contents/{*}Key")
    out.append({"satellite":satellite,"prefix_generation_month":"202608","key":key})
    print(out[-1],flush=True)
(root/"august-orbit-catalog.json").write_text(json.dumps(out,indent=2))

