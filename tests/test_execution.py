import os

import pytest

from agent.tools.execution import PythonRunner
from agent.tools.filesystem import FilesystemTools


@pytest.fixture
def runner(tmp_path):
    image = os.environ.get("RESIDENT_TEST_IMAGE")
    if not image:
        pytest.skip(
            "Set RESIDENT_TEST_IMAGE to a trusted local immutable image ID for physical execution tests"
        )
    return FilesystemTools(tmp_path), PythonRunner(tmp_path, image)


@pytest.mark.docker
def test_real_execution_network_credentials_and_readonly(runner):
    fs, executor = runner
    fs.write_file(
        "probe.py",
        """import os, socket
assert not any(k in os.environ for k in ["NEBIUS_API_KEY", "MNEME_API_KEY", "MNEME_LOCAL_API_KEY"])
assert os.getuid() == 65534
try:
    open('/input/main.py', 'w')
except OSError:
    pass
else:
    raise AssertionError('source was writable')
s = socket.socket()
s.settimeout(.2)
try:
    s.connect(('1.1.1.1', 443))
except OSError:
    pass
else:
    raise AssertionError('external network connected')
print('isolation probe passed')
""",
    )
    result = executor.run_python("probe.py")
    assert result["status"] == "passed", result
    assert "isolation probe passed" in result["output"]
    assert fs.read_file("probe.py")["sha256"] == result["source_sha256"]


@pytest.mark.docker
def test_output_and_cpu_bounded(runner):
    fs, executor = runner
    fs.write_file("output.py", "print('x'*20000)")
    result = executor.run_python("output.py")
    assert result["status"] == "output_limit" and len(result["output"].encode()) <= 16000
    fs.write_file("cpu.py", "while True: pass")
    result = executor.run_python("cpu.py")
    assert result["status"] in {"failed", "timeout"}
