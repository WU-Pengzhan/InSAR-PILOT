
from pathlib import Path
import hashlib, json, re, subprocess
from urllib.parse import unquote
root=Path("/home/griffin/projects/insar-pilot")
evidence=root/"artifacts/p01-design-2026-09-06"
archive=root/"archive/guidance/2026-09-06-before-p01-design"
entries=json.loads((archive/"manifest.json").read_text())
for entry in entries:
    assert hashlib.sha256((archive/entry["path"]).read_bytes()).hexdigest()==entry["sha256"], entry["path"]
baseline=json.loads((evidence/"product-baseline.json").read_text())
excluded={".git",".pytest_cache",".mypy_cache",".ruff_cache","__pycache__","node_modules","dist",".venv","site","build"}
current={}
for name in ["src","frontend","tests","scripts"]:
    for p in (root/name).rglob("*"):
        rel=p.relative_to(root)
        if p.is_file() and not excluded.intersection(rel.parts):
            current[str(rel)]=hashlib.sha256(p.read_bytes()).hexdigest()
for name in ["AGENTS.md","pyproject.toml","uv.lock","environment.yml","install.sh"]:
    current[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
assert current==baseline, "Product file set or content changed"
docs=[root/e["path"] for e in entries if e["path"].endswith(".md")]
docs += [root/"docs/architecture/p01-search-download.md",root/"docs/handoff/records/2026-09-06-p01-search-download-design.md"]
links=0
for p in docs:
    body=p.read_text()
    for line in body.splitlines():
        assert line.rstrip()==line, f"Trailing whitespace: {p}"
    for raw in re.findall(r"\]\(([^)]+)\)", body):
        target=unquote(raw.split("#",1)[0])
        if not target or re.match(r"[a-zA-Z]+:",target):
            continue
        assert (p.parent/target).resolve().exists(), (str(p),target)
        links+=1
diff=subprocess.run(["git","diff","--check"],cwd=root,capture_output=True,text=True)
(evidence/"git-diff-check.log").write_text(diff.stdout+diff.stderr)
assert diff.returncode==0, diff.stdout+diff.stderr
design=(root/"docs/architecture/p01-search-download.md").read_text()
assert len(re.findall(r"^\| A\d\d \|",design,re.M))==16
render=Path("/tmp/insar-pilot-p01-design-docs/architecture/p01-search-download/index.html").read_text()
assert "P01｜检索与下载｜页面设计" in render and "<table>" in render and "A16" in render
summary={"result":"PASS","archived_files_verified":len(entries),"unchanged_product_files":len(current),"documents_checked":len(docs),"local_links_checked":links,"acceptance_scenarios":16,"git_diff_check":"PASS","rendered_design_html":"PASS"}
(evidence/"validation.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(summary,ensure_ascii=False))
