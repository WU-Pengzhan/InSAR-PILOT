"""Read real public EOF samples through the installed ISCE2 parser."""
import json
import re
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import isce
from isceobj.Sensor.TOPS.Sentinel1 import Sentinel1, s1_findOrbitFile

root = Path("/home/griffin/projects/insar-pilot/artifacts/p01-implementation-2026-09-06")
out=[]
for path in sorted(root.glob("S1[CD]*.EOF")):
    start = datetime.strptime(re.search(r"_V(\d{8}T\d{6})", path.name)[1], "%Y%m%dT%H%M%S") + timedelta(hours=12)
    stop = start + timedelta(seconds=30)
    sensor=Sentinel1()
    sensor.configure()
    sensor.product=SimpleNamespace(bursts=[SimpleNamespace(sensingStart=start,sensingStop=stop)])
    sensor.orbitFile=str(path)
    orbit=sensor.extractPreciseOrbit()
    with tempfile.TemporaryDirectory(prefix="pilot-isce-orbit-") as temporary:
        copied=Path(temporary)/path.name
        shutil.copyfile(path,copied)
        from insar_pilot.download.orbit_service import OrbitDownloadService
        from insar_pilot.download.models import SceneRecord
        sid=f"{path.name[:3]}_IW_SLC__1SDV_{start:%Y%m%dT%H%M%S}_{stop:%Y%m%dT%H%M%S}_TEST"
        OrbitDownloadService.validate(copied,SceneRecord(sid,start.isoformat(),path.name[:3],"",0,"",0))
        chosen=s1_findOrbitFile(temporary,start,stop,mission=path.name[:3])
        exact=chosen==str(copied)
    vector=orbit.interpolateOrbit(start+timedelta(seconds=15),method="hermite")
    out.append({"satellite":path.name[:3],"file":path.name,"isce_selected_exact_file":exact,
                "state_vectors":len(orbit),"position_m":list(vector.getPosition()),
                "velocity_mps":list(vector.getVelocity()),"scope":"EOF parse and interpolation; no SAR computation"})
(root/"isce-eof-probe.json").write_text(json.dumps(out,indent=2))
print(json.dumps(out))

