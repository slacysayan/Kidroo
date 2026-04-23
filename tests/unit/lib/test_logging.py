import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from agents.lib.logging import log_step

@pytest.mark.asyncio
async def test_log_step():
    # Setup mocks
    mock_supabase = MagicMock() # The client itself has sync methods like .table()

    mock_table = MagicMock()
    mock_supabase.table.return_value = mock_table

    mock_insert = MagicMock()
    mock_table.insert.return_value = mock_insert

    # execute() is the one that returns a coroutine in AsyncClient
    mock_execute = AsyncMock()
    mock_insert.execute = mock_execute

    # get_supabase is now an async function that returns a sync-created client
    with patch("agents.lib.logging.get_supabase", AsyncMock(return_value=mock_supabase)):
        await log_step(
            job_id="job_123",
            agent="orchestrator",
            step="status",
            message="started",
            metadata={"test": "data"}
        )

    mock_table.insert.assert_called_once_with({
        "job_id": "job_123",
        "video_id": None,
        "agent": "orchestrator",
        "step": "status",
        "message": "started",
        "metadata": {"test": "data"},
        "trace_id": None
    })
    mock_execute.assert_called_once()
