"""Middleware stuff"""
# importing annotations from future blows up fastapi dependency injection
from typing import Optional
from dataclasses import dataclass, field
import logging
import asyncio

from sqlalchemy.engine.url import URL
from starlette.types import Receive, Scope, Send
from fastapi import FastAPI
from gino import Gino
from gino.exceptions import UninitializedError
from arkia11nmodels import dbconfig

# We can't mokeypatch gino-starlette into models this late
LOGGER = logging.getLogger(__name__)

# FIXME: this should probably be in some common library of ours


@dataclass
class DBWrapper:  # pylint: disable=R0902
    """Handle app db connection stuff"""

    gino: Gino
    dsn: URL = field(default=dbconfig.DSN)
    retry_limit: int = field(default=dbconfig.RETRY_LIMIT)
    retry_interval: int = field(default=dbconfig.RETRY_INTERVAL)
    echo: bool = field(default=dbconfig.ECHO)
    min_size: int = field(default=dbconfig.POOL_MIN_SIZE)
    max_size: int = field(default=dbconfig.POOL_MAX_SIZE)
    ssl: str = field(default=dbconfig.SSL)
    use_for_request: bool = field(default=dbconfig.USE_CONNECTION_FOR_REQUEST)

    async def bind_gino(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Bind gino to db"""
        if self.gino._bind is not None:  # pylint: disable=W0212
            LOGGER.warning("Already bound")
            return
        await self.gino.set_bind(
            self.dsn,
            echo=self.echo,
            min_size=self.min_size,
            max_size=self.max_size,
            ssl=self.ssl,
            loop=loop,
        )

    async def app_startup_event(self) -> None:
        """App startup callback, connect to db or die"""
        LOGGER.info("Connecting to the database: {!r}".format(self.dsn))
        retries = 0
        while True:
            retries += 1
            try:
                await self.bind_gino()
                break
            except Exception as exc:  # pylint: disable=W0703
                LOGGER.error("database connection failed {}".format(exc))
                # TODO: Check that it's a connection error, otherwise just raise immediately
                if retries < self.retry_limit:
                    LOGGER.info("Waiting for the database to start...")
                    await asyncio.sleep(self.retry_interval)
                else:
                    LOGGER.error("Cannot connect to the database; max retries reached.")
                    raise
        msg = "Database connection pool created: {}"
        LOGGER.info(
            msg.format(repr(self.gino.bind)),
            extra={"color_message": msg.format(self.gino.bind.repr(color=True))},
        )

    async def app_shutdown_event(self) -> None:
        """On app shutdown close the db connection"""
        try:
            msg = "Closing database connection: {}"
            LOGGER.info(
                msg.format(repr(self.gino.bind)),
                extra={"color_message": msg.format(self.gino.bind.repr(color=True))},
            )
            ginobound = self.gino.pop_bind()
            await ginobound.close()
            msg = "Closed database connection: {}"
            LOGGER.info(
                msg.format(repr(ginobound)),
                extra={"color_message": msg.format(ginobound.repr(color=True))},
            )
        except UninitializedError as exc:
            LOGGER.exception("Ignoring {} during close".format(exc))

    def init_app(self, app: FastAPI) -> None:
        """Ibject into app"""
        app.add_event_handler("startup", self.app_startup_event)
        app.add_event_handler("shutdown", self.app_shutdown_event)
        app.add_middleware(DBConnectionMiddleware, dbwrap=self)


class DBConnectionMiddleware:  # pylint: disable=R0903
    """Middleware that handles request connection pooling"""

    def __init__(self, app: FastAPI, dbwrap: DBWrapper) -> None:
        self.app = app
        self.dbwrap = dbwrap
        self._conn_for_req = self.dbwrap.use_for_request

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Not going to handle this, pass onwards
        if scope["type"] != "http" or not self._conn_for_req:
            await self.app(scope, receive, send)
            return

        # Get and release connection
        scope["connection"] = await self.dbwrap.gino.acquire(lazy=True)
        try:
            await self.app(scope, receive, send)
        finally:
            conn = scope.pop("connection", None)
            if conn is not None:
                await conn.release()
