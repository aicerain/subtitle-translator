import tempfile
import unittest
from pathlib import Path

from core.downloader import DownloadError, download_video_from_url, is_video_url


class FakeYoutubeDL:
    instances = []

    def __init__(self, options):
        self.options = options
        self.progress_hooks = options.get("progress_hooks", [])
        FakeYoutubeDL.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url, download=True):
        for hook in self.progress_hooks:
            hook({
                "status": "downloading",
                "downloaded_bytes": 25,
                "total_bytes": 100,
                "filename": "/tmp/video.part",
            })
        for hook in self.progress_hooks:
            hook({
                "status": "finished",
                "filename": "/tmp/video.mp4",
            })
        return {
            "id": "abc123",
            "title": "Demo Video",
            "ext": "mp4",
            "requested_downloads": [{"filepath": str(Path(self.options["paths"]["home"]) / "Demo Video [abc123].mp4")}],
        }


class FailingYoutubeDL(FakeYoutubeDL):
    def extract_info(self, url, download=True):
        raise RuntimeError("login required")


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        FakeYoutubeDL.instances = []

    def test_is_video_url_accepts_http_and_https_only(self):
        self.assertTrue(is_video_url("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(is_video_url("http://bilibili.com/video/BV123"))
        self.assertFalse(is_video_url("/Users/me/movie.mp4"))
        self.assertFalse(is_video_url("ftp://example.com/video.mp4"))
        self.assertFalse(is_video_url(""))

    def test_download_video_reports_progress_and_returns_downloaded_path(self):
        messages = []
        with tempfile.TemporaryDirectory() as tmp:
            result = download_video_from_url(
                "https://www.youtube.com/watch?v=abc",
                tmp,
                progress_cb=messages.append,
                ydl_cls=FakeYoutubeDL,
            )

        self.assertEqual(result.title, "Demo Video")
        self.assertEqual(result.video_id, "abc123")
        self.assertEqual(Path(result.path).name, "Demo Video [abc123].mp4")
        self.assertTrue(any("下载进度: 25%" in msg for msg in messages))
        self.assertTrue(any("下载完成" in msg for msg in messages))

    def test_download_video_uses_safe_output_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_video_from_url(
                "https://www.tiktok.com/@demo/video/1",
                tmp,
                ydl_cls=FakeYoutubeDL,
            )

        options = FakeYoutubeDL.instances[0].options
        self.assertEqual(options["paths"]["home"], tmp)
        self.assertIn("%(title).200B", options["outtmpl"])
        self.assertIn("%(id)s", options["outtmpl"])
        self.assertEqual(options["merge_output_format"], "mp4")
        self.assertIn("mp4", options["format"])

    def test_download_video_wraps_downloader_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(DownloadError, "login required"):
                download_video_from_url(
                    "https://www.douyin.com/video/1",
                    tmp,
                    ydl_cls=FailingYoutubeDL,
                )


if __name__ == "__main__":
    unittest.main()
