from fastapi import APIRouter
from .routers import utils as utils_router
from .routers import agent as agent_router
from .routers import feedback as feedback_router
from .routers import interviews as interviews_router
from .routers import share as share_router


def include_routers(router: APIRouter) -> None:
    router.include_router(utils_router.router)
    router.include_router(agent_router.router)
    router.include_router(feedback_router.router)
    router.include_router(interviews_router.router)
    router.include_router(share_router.router)


