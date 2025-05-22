import taskiq_fastapi
from taskiq import AsyncBroker, InMemoryBroker, ZeroMQBroker

from med_rag_server.settings import settings

broker: AsyncBroker = ZeroMQBroker()

if settings.environment.lower() == "pytest":
    broker = InMemoryBroker()

taskiq_fastapi.init(
    broker,
    "med_rag_server.web.application:get_app",
)
