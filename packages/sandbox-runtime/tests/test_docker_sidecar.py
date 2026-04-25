"""Tests for Docker sidecar startup."""

from unittest.mock import AsyncMock, MagicMock, patch

from sandbox_runtime.entrypoint import SandboxSupervisor


def _make_supervisor() -> SandboxSupervisor:
    with patch.dict(
        "os.environ",
        {
            "SANDBOX_ID": "test-sandbox",
            "REPO_OWNER": "acme",
            "REPO_NAME": "app",
            "SESSION_CONFIG": "{}",
        },
    ):
        return SandboxSupervisor()


class TestDockerSidecar:
    async def test_skips_when_disabled(self):
        sup = _make_supervisor()
        sup.log = MagicMock()

        with patch.dict("os.environ", {"OPENINSPECT_DOCKER_ENABLED": "false"}, clear=False):
            await sup.start_docker()

        sup.log.info.assert_called_with(
            "docker.skip", reason="OPENINSPECT_DOCKER_ENABLED not true"
        )

    async def test_uses_existing_daemon(self):
        sup = _make_supervisor()
        sup.log = MagicMock()
        sup._docker_ready = AsyncMock(return_value=True)

        with patch.dict("os.environ", {"OPENINSPECT_DOCKER_ENABLED": "true"}, clear=False):
            await sup.start_docker()

        sup.log.info.assert_called_with("docker.ready", source="existing")

    async def test_starts_dockerd_when_not_ready(self):
        sup = _make_supervisor()
        sup.log = MagicMock()
        readiness = [False, True]

        async def fake_ready(timeout_seconds=3.0):
            return readiness.pop(0)

        dockerd_proc = MagicMock()
        dockerd_proc.returncode = None
        dockerd_proc.pid = 123
        dockerd_proc.stdout = None

        with (
            patch.dict("os.environ", {"OPENINSPECT_DOCKER_ENABLED": "true"}, clear=False),
            patch("sandbox_runtime.entrypoint.shutil.which", return_value="/usr/bin/dockerd"),
            patch("sandbox_runtime.entrypoint.Path.mkdir"),
            patch(
                "sandbox_runtime.entrypoint.asyncio.create_subprocess_exec",
                new_callable=AsyncMock,
                return_value=dockerd_proc,
            ) as mock_exec,
            patch.object(sup, "_docker_ready", side_effect=fake_ready),
        ):
            await sup.start_docker()

        mock_exec.assert_called_once()
        args = mock_exec.call_args.args
        assert args[0] == "dockerd"
        assert "--host=unix:///var/run/docker.sock" in args
        assert "--storage-driver=vfs" in args
        sup.log.info.assert_any_call("docker.ready", source="started", pid=123)

    async def test_autostarts_before_start_hook(self):
        sup = _make_supervisor()
        order = []

        sup.perform_git_sync = AsyncMock(return_value=True)
        sup.run_setup_script = AsyncMock(return_value=True)
        sup.start_opencode = AsyncMock()
        sup.start_bridge = AsyncMock()
        sup.monitor_processes = AsyncMock()
        sup.shutdown = AsyncMock()

        async def start_docker():
            order.append("docker")

        async def run_start_script():
            order.append("start")
            return True

        sup.start_docker = AsyncMock(side_effect=start_docker)
        sup.run_start_script = AsyncMock(side_effect=run_start_script)

        with (
            patch.dict("os.environ", {"OPENINSPECT_DOCKER_AUTOSTART": "true"}, clear=False),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop.return_value.add_signal_handler = MagicMock()
            await sup.run()

        assert order == ["docker", "start"]
