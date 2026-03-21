import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestFeedbackService:
    @pytest.mark.asyncio
    async def test_disabled_feedback_returns_unrecorded(self):
        from backend.config.settings import FeedbackSettings
        from backend.models.schemas import FeedbackRequest
        from backend.services.feedback_service import FeedbackService

        service = FeedbackService(FeedbackSettings(enabled=False))
        result = await service.record(FeedbackRequest(response_id="resp-1", score=5))

        assert result.recorded is False

    @pytest.mark.asyncio
    async def test_out_of_range_feedback_is_not_stored(self, tmp_path):
        from backend.config.settings import FeedbackSettings
        from backend.models.schemas import FeedbackRequest
        from backend.services.feedback_service import FeedbackService

        service = FeedbackService(
            FeedbackSettings(
                enabled=True,
                store_path=str(tmp_path / "feedback.db"),
                min_score=1,
                max_score=5,
            )
        )
        await service.init()
        result = await service.record(FeedbackRequest(response_id="resp-2", score=9))
        await service.close()

        assert result.recorded is False


class TestVoiceAPI:
    @pytest.mark.asyncio
    async def test_tts_uses_mp3_headers_for_gtts(self):
        from backend.api.v1.voice import tts
        from backend.models.schemas import TTSRequest

        class FakeVoiceService:
            def __init__(self) -> None:
                self.cfg = SimpleNamespace(tts_engine="gtts")

            async def synthesize(self, text, engine=None, speed=1.0):
                return b"fake-mp3"

        response = await tts(TTSRequest(text="hello"), svc=FakeVoiceService())

        assert response.media_type == "audio/mpeg"
        assert response.headers["content-disposition"] == "inline; filename=response.mp3"


class TestSystemAPI:
    @pytest.mark.asyncio
    async def test_status_includes_environment(self):
        from backend.api.v1.system import status
        from backend.config.settings import settings

        class FakeMonitoring:
            def loaded_models(self):
                return []

            def total_requests(self):
                return 0

            def avg_latency(self):
                return 0.0

        class FakeFeedback:
            def total_count(self):
                return 0

        response = await status(mon=FakeMonitoring(), fb=FakeFeedback())

        assert response.data["environment"] == settings.server.environment
