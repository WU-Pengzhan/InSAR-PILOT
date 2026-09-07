<p align="center"><img src="docs/assets/branding/logo.png" width="520" alt="InSAR-PILOT"></p>

<h1 align="center">A clearer workspace for radar imagery.</h1>
<p align="center">Find scenes, manage downloads, and organize your research in one local workbench.</p>
<p align="center">Runs locally · Works in your browser · English & Chinese · Open source</p>
<p align="center"><a href="https://github.com/WU-Pengzhan/InSAR-PILOT/releases/tag/v1.5.0">Get 1.5.0</a> · <a href="docs/en/quickstart.md">Quickstart</a> · <a href="README.md">中文</a></p>

## Your SAR / InSAR workspace

InSAR-PILOT brings projects, maps, scene selections, and background tasks into a single interface. Start with a study area or return to an existing project, keep your imagery organized, and see where each download is going.

**Version 1.5.0 focuses on Sentinel-1 project management, search, and downloads.** Data preparation, processing parameters, run monitoring, and product review will be refined in subsequent releases.

![The Web search workspace](docs/assets/screenshots/web-search.png)

## Find scenes on the map

Draw your study area and filter by date, satellite, orbit, and polarization. Compare scene footprints with the results list, then keep a selection while you refine your search. Choose Sentinel-1 A, B, C, and D individually.

Preview your selection, optional orbit/elevation data, and destination before creating a project, adding to an existing project, or downloading to the shared library.

## Give each study a home

Create or open a project, return through the recent-project list, or explore imagery first. The project browser keeps your files within reach; data, processing work, and products have separate places. Reuse verified sources across projects where supported.

![Project entry screen](docs/assets/screenshots/web-home.png)

## Keep downloads in view

Track each batch, inspect its scenes and save location, and pause, resume, cancel, or retry from the download center. Search by scene, batch, or path and browse earlier attempts. Background tasks continue when you switch projects or close the browser.

## Make room for your work

Switch between English and Chinese, choose a light or dark theme, resize the project pane, and collapse the inspector to give the map more space. Use a Linux browser on Ubuntu or a Windows browser connected to WSL. One window uses the workbench at a time; other windows wait and reconnect when it becomes available.

## What is available today?

| Area | Version 1.5.0 |
| --- | --- |
| Search & downloads | Map search, persistent selections, acquisition preview, and download controls |
| Data & preparation | Basic input capabilities; full page refinement pending |
| Parameters & generation | Backend capabilities retained; professional forms pending |
| Run | Task, log, and history foundations; complete page refinement pending |
| Products & QC | Basic product capabilities; professional review page pending |

Sentinel-1 is the current priority. Existing NISAR backend capabilities remain available; its dedicated experience comes later. Real-account sustained downloads and complete scientific workflows still have separate acceptance work. See the [release notes](docs/releases/1.5.0.md).

## Get started

Download [1.5.0](https://github.com/WU-Pengzhan/InSAR-PILOT/releases/tag/v1.5.0), follow the [installation guide](docs/en/installation.md), then explore your first study area with the [quickstart](docs/en/quickstart.md).

For questions and suggestions, open an [issue](https://github.com/WU-Pengzhan/InSAR-PILOT/issues). To contribute, read [CONTRIBUTING](CONTRIBUTING.md).

## Open source & acknowledgements

Licensed under [Apache-2.0](LICENSE). Thanks to [ISCE2](https://github.com/isce-framework/isce2), [ISCE3](https://github.com/isce-framework/isce3), ASF, and the wider open-source radar community. InSAR-PILOT is an independent project.
