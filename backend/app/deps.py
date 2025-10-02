from fastapi import APIRouter
from .routers import utils as utils_router
from .routers import agent as agent_router


def include_routers(router: APIRouter) -> None:
    router.include_router(utils_router.router)
    router.include_router(agent_router.router)


