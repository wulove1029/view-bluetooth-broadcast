import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import view_bluetooth_broadcast as app


class UpdateHttpTests(unittest.TestCase):
    def test_update_http_get_uses_certifi_without_environment_proxy(self):
        response = Mock()
        response.status_code = 200

        with patch("view_bluetooth_broadcast.requests.Session") as session_cls, \
             patch("view_bluetooth_broadcast._ca_bundle_path", return_value="C:/bundle/cacert.pem"):
            session = session_cls.return_value
            session.get.return_value = response

            result = app._update_http_get("https://example.test/releases/latest", timeout=(2, 5))

        self.assertIs(result, response)
        self.assertIs(session.trust_env, False)
        session.get.assert_called_once_with(
            "https://example.test/releases/latest",
            headers=app.UPDATE_HTTP_HEADERS,
            timeout=(2, 5),
            verify="C:/bundle/cacert.pem",
            stream=False,
        )
        response.raise_for_status.assert_called_once_with()

    def test_downloader_uses_update_http_get_for_https_downloads(self):
        chunks = [b"abc", b"def"]
        response = Mock()
        response.headers = {"Content-Length": "6"}
        response.iter_content.return_value = chunks

        with TemporaryDirectory() as tmp, \
             patch("view_bluetooth_broadcast._update_http_get", return_value=response) as http_get:
            progress = Mock()
            done = Mock()
            error = Mock()
            dest = Path(tmp) / "BLE-Scanner.exe"

            downloader = app.UpdateDownloader("https://example.test/BLE-Scanner.exe", dest, progress, done, error)
            downloader.run()

            http_get.assert_called_once_with("https://example.test/BLE-Scanner.exe", timeout=(5, 30), stream=True)
            self.assertEqual(dest.read_bytes(), b"abcdef")
            progress.assert_called_with(100)
            done.assert_called_once_with(dest)
            error.assert_not_called()

    def test_update_result_uses_qt_signal_for_cross_thread_delivery(self):
        gui = SimpleNamespace(
            _update_signals=SimpleNamespace(update_result=SimpleNamespace(emit=Mock()))
        )

        app.BluetoothBroadcastGUI._on_update_result(gui, "newer", "1.2.3", "https://example.test/app.exe", "", True)

        gui._update_signals.update_result.emit.assert_called_once_with(
            "newer",
            "1.2.3",
            "https://example.test/app.exe",
            "",
            True,
        )

    def test_update_script_waits_for_pyinstaller_processes_before_restart(self):
        script = app._build_update_script(
            new_exe=Path("C:/Temp/BLE-Scanner-1.0.15.exe"),
            current_exe=Path("C:/Program Files/BLE/BLE-Scanner.exe"),
            current_pid=111,
        )

        self.assertIn('set "OLD_PID=111"', script)
        self.assertIn("tasklist /FI", script)
        self.assertIn(":wait_old_process", script)
        self.assertNotIn("PARENT_PID", script)
        self.assertNotIn(":wait_parent_process", script)
        self.assertIn(":replace_retry", script)
        self.assertIn('set "CURRENT_EXE=C:\\Program Files\\BLE\\BLE-Scanner.exe"', script)
        self.assertIn('start "" "%CURRENT_EXE%"', script)


if __name__ == "__main__":
    unittest.main()
