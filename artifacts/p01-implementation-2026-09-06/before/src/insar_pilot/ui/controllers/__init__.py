"""Qt-coupled page controllers extracted from the MainWindow shell."""

from insar_pilot.ui.controllers.download_controller import DownloadController
from insar_pilot.ui.controllers.results_controller import ResultsController
from insar_pilot.ui.controllers.run_controller import RunController
from insar_pilot.ui.controllers.setup_controller import SetupController

__all__ = [
    "DownloadController",
    "ResultsController",
    "RunController",
    "SetupController",
]
