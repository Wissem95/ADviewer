import pytest
from unittest.mock import patch, MagicMock
import subprocess


def test_start_backend_returns_process():
    """start_backend retourne un subprocess Popen."""
    from localcoder.workspace import start_backend

    # Mock subprocess et requests pour éviter de lancer un vrai serveur
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # Processus vivant

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("localcoder.workspace.subprocess.Popen", return_value=mock_process):
        with patch("localcoder.workspace.requests.get", return_value=mock_response):
            proc = start_backend()

    assert proc is mock_process


def test_start_backend_raises_on_timeout():
    """Si le health check échoue 10 fois → TimeoutError."""
    from localcoder.workspace import start_backend

    mock_process = MagicMock()
    mock_process.poll.return_value = None

    with patch("localcoder.workspace.subprocess.Popen", return_value=mock_process):
        with patch("localcoder.workspace.requests.get", side_effect=Exception("Connection refused")):
            with patch("localcoder.workspace.time.sleep"):  # Skip les sleeps
                with pytest.raises(TimeoutError, match="Backend"):
                    start_backend()


def test_start_backend_raises_if_process_dies():
    """Si le processus meurt pendant le health check → RuntimeError."""
    from localcoder.workspace import start_backend

    mock_process = MagicMock()
    mock_process.poll.return_value = 1  # Exit code non-zéro
    mock_process.stderr = MagicMock()
    mock_process.stderr.read.return_value = b"Error"

    with patch("localcoder.workspace.subprocess.Popen", return_value=mock_process):
        with patch("localcoder.workspace.requests.get", side_effect=Exception("refused")):
            with patch("localcoder.workspace.time.sleep"):
                with pytest.raises(RuntimeError, match="Backend"):
                    start_backend()
