import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from core.downloader import DownloadResult


qtcore = types.ModuleType("PyQt6.QtCore")


class FakeQThread:
    def __init__(self):
        pass


def fake_pyqt_signal(*_args, **_kwargs):
    class Signal:
        def emit(self, *_args, **_kwargs):
            pass
    return Signal()


qtcore.QThread = FakeQThread
qtcore.pyqtSignal = fake_pyqt_signal
pyqt6 = types.ModuleType("PyQt6")
sys.modules.setdefault("PyQt6", pyqt6)
sys.modules.setdefault("PyQt6.QtCore", qtcore)

from core.worker import SubtitleWorker


class WorkerUrlTests(unittest.TestCase):
    def test_prepare_video_input_downloads_url_to_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloaded = Path(tmp) / "Demo [abc].mp4"

            worker = SubtitleWorker(
                video_path="https://www.youtube.com/watch?v=abc",
                config={},
                target_language="zh",
                output_dir=tmp,
            )

            with patch("core.worker.download_video_from_url") as fake_download:
                fake_download.return_value = DownloadResult(
                    path=str(downloaded),
                    title="Demo",
                    video_id="abc",
                )

                path = worker._prepare_video_input()

        self.assertEqual(path, str(downloaded))
        fake_download.assert_called_once()
        self.assertEqual(fake_download.call_args.args[0], "https://www.youtube.com/watch?v=abc")
        self.assertEqual(fake_download.call_args.args[1], tmp)


if __name__ == "__main__":
    unittest.main()
