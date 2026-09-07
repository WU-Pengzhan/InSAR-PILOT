"""Real lightweight subprocess tests; no numerical processors or display required."""

import os
import sys
import threading
import time
from pathlib import Path

from insar_pilot.domain.engine import PipelineDefinition, Profile, StepDefinition
from insar_pilot.infrastructure.engine_store import EngineStore
from insar_pilot.infrastructure.job_executor import LocalJobExecutor


def running_job(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"input")
    store = EngineStore.create(tmp_path / "project", "Job")
    artifact = store.register_source(source, "Sentinel1SLC", Profile.SENTINEL1_TOPS)
    store.attach_dataset([artifact["artifact_id"]], Profile.SENTINEL1_TOPS, 1)
    definition = PipelineDefinition("test.job", Profile.SENTINEL1_TOPS, (StepDefinition("stage", "Stage"),))
    pid = store.add_pipeline(definition, {"input": [artifact["artifact_id"]]}, {}, {}, 2)
    execution = store.submit(store.create_plan(pid)["plan_id"])
    rid = execution["run_ids"][0]
    store.begin(rid, [[sys.executable]], {})
    return store, rid


def test_stdout_stderr_are_durable_and_separate(tmp_path):
    store, rid = running_job(tmp_path)
    code = LocalJobExecutor().execute(
        store,
        rid,
        [sys.executable, "-c", "import sys; print('output'); print('diagnostic',file=sys.stderr); sys.exit(7)"],
        os.environ.copy(),
    )
    assert code == 7
    run = store.run(rid)
    assert Path(run["stdout_log"]).read_text().strip() == "output"
    assert Path(run["stderr_log"]).read_text().strip() == "diagnostic"


def test_cancel_stops_the_process_group(tmp_path):
    store, rid = running_job(tmp_path)
    results = []
    worker = threading.Thread(
        target=lambda: results.append(
            LocalJobExecutor().execute(
                store, rid, [sys.executable, "-c", "import time; time.sleep(60)"], os.environ.copy()
            )
        )
    )
    worker.start()
    deadline = time.monotonic() + 5
    while store.list_objects("jobs")[0]["pid"] is None and time.monotonic() < deadline:
        time.sleep(0.05)
    store.cancel(store.run(rid)["job_id"])
    worker.join(timeout=8)
    assert not worker.is_alive()
    assert results[0] != 0
