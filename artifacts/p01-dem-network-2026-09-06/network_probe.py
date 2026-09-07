
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import requests, time, json
out=Path("/home/griffin/projects/insar-pilot/artifacts/p01-dem-network-2026-09-06")
url="https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N34_00_E108_00_DEM/Copernicus_DSM_COG_10_N34_00_E108_00_DEM.tif"
result={"time":datetime.now().astimezone().isoformat(),"source":url,"network":"WSL direct, trust_env=False; no credentials","payload_budget_bytes":24*1024*1024,"runs":[]}
def session():
    s=requests.Session();s.trust_env=False;return s
try:
    with session() as s:
        start=time.monotonic()
        with s.head(url,timeout=(8,12)) as r:
            r.raise_for_status()
            size=int(r.headers["Content-Length"])
            result["head"]={"status":r.status_code,"size":size,"etag":r.headers.get("ETag"),"seconds":round(time.monotonic()-start,3),"accept_ranges":r.headers.get("Accept-Ranges")}
    total=4*1024*1024
    assert size>=total*6
    for trial,workers in enumerate([1,4,8,8,4,1]):
        offset=trial*total
        width=total//workers
        def get(index):
            lo=offset+index*width;hi=lo+width-1
            t=time.monotonic(); count=0
            try:
                with session() as s:
                    with s.get(url,headers={"Range":f"bytes={lo}-{hi}","Accept-Encoding":"identity"},stream=True,timeout=(8,12)) as r:
                        if r.status_code!=206:raise ValueError("range_not_206")
                        if r.headers.get("Content-Range")!=f"bytes {lo}-{hi}/{size}":raise ValueError("range_mismatch")
                        if r.headers.get("ETag")!=result["head"]["etag"]:raise ValueError("object_changed")
                        for chunk in r.iter_content(65536):
                            count+=len(chunk)
                            if count>width or time.monotonic()-t>25:raise ValueError("probe_limit")
                        if count!=width:raise ValueError("size_mismatch")
                return {"bytes":count,"ok":True}
            except Exception as exc:return {"bytes":count,"ok":False,"error_type":type(exc).__name__}
        start=time.monotonic()
        with ThreadPoolExecutor(max_workers=workers) as pool:parts=list(pool.map(get,range(workers)))
        elapsed=time.monotonic()-start; count=sum(p["bytes"] for p in parts)
        run={"workers":workers,"bytes":count,"seconds":round(elapsed,3),"MiB_s":round(count/1024**2/elapsed,3),"ok":all(p["ok"] for p in parts),"errors":[p["error_type"] for p in parts if not p["ok"]]}
        result["runs"].append(run)
        print(json.dumps(run),flush=True)
        if not run["ok"]:break
except Exception as exc:result["probe_error_type"]=type(exc).__name__
finally:
    (out/"network-probe.json").write_text(json.dumps(result,indent=2)+"\n")
    print("Saved network-probe.json",flush=True)
