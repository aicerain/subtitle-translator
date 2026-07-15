import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import cache, video
from core.transcriber import build_transcriber


class LowVolumeAudioTests(unittest.TestCase):
    def test_extract_audio_normalizes_loudness_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "audio.wav"
            with patch("core.video.find_ffmpeg", return_value="ffmpeg"), patch(
                "core.video.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                video.extract_audio("input.mp4", str(output))

        command = run.call_args.args[0]
        self.assertIn("-af", command)
        self.assertIn("loudnorm=I=-16:LRA=11:TP=-1.5", command)

    def test_extract_audio_can_skip_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "audio.wav"
            with patch("core.video.find_ffmpeg", return_value="ffmpeg"), patch(
                "core.video.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, "", ""),
            ) as run:
                video.extract_audio(
                    "input.mp4",
                    str(output),
                    normalize_loudness=False,
                )

        self.assertNotIn("-af", run.call_args.args[0])

    def test_low_volume_settings_change_asr_cache_fingerprint(self):
        base = {
            "whisper_vad_threshold": 0.15,
            "whisper_audio_normalization": True,
        }
        disabled = dict(base, whisper_audio_normalization=False)

        self.assertNotEqual(
            cache.asr_fingerprint(base, "auto"),
            cache.asr_fingerprint(disabled, "auto"),
        )

    def test_transcriber_defaults_to_low_volume_friendly_vad_threshold(self):
        transcriber = build_transcriber({})

        self.assertEqual(transcriber.vad_threshold, 0.15)


if __name__ == "__main__":
    unittest.main()
