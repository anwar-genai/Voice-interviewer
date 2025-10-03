from fastapi import APIRouter
from .routers import utils as utils_router
from .routers import agent as agent_router
from .routers import feedback as feedback_router
from .routers import analytics as analytics_router


def include_routers(router: APIRouter) -> None:
    router.include_router(utils_router.router)
    router.include_router(agent_router.router)
    router.include_router(feedback_router.router)
    router.include_router(analytics_router.router)


