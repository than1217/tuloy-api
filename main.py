from fastapi import FastAPI
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import mysql.connector
from mysql.connector import Error

import database
from database import get_db_config

from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
try:
    from sshtunnel import SSHTunnelForwarder
except ImportError:
    SSHTunnelForwarder = None

from utils import cache_key_builder
from routers import auth, beneficiaries

load_dotenv(override=True)

CACHE_EXPIRE_SECONDS = int(os.getenv("CACHE_EXPIRE_SECONDS", "1200"))
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    load_dotenv(override=True)
    database.DB_CONFIG.update({
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "database": os.getenv("DB_DATABASE"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    })

    # Initialize Redis for caching (with automatic InMemoryBackend fallback)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        redis_client = aioredis.from_url(redis_url)
        await redis_client.ping()
        FastAPICache.init(
            RedisBackend(redis_client),
            prefix="tuloy-api-cache",
            expire=CACHE_EXPIRE_SECONDS,
            key_builder=cache_key_builder,
        )
        print(f"Redis cache initialized at {redis_url} (TTL: {CACHE_EXPIRE_SECONDS}s)")
    except Exception as e:
        if redis_client is not None:
            await redis_client.aclose()
            redis_client = None
        FastAPICache.init(
            InMemoryBackend(),
            prefix="tuloy-api-cache",
            expire=CACHE_EXPIRE_SECONDS,
            key_builder=cache_key_builder,
        )
        print(
            f"Redis unavailable ({e}). Falling back to InMemoryBackend (TTL: {CACHE_EXPIRE_SECONDS}s)"
        )

    ssh_host = os.getenv("SSH_HOST")
    try:
        try:
            if ssh_host:
                if SSHTunnelForwarder is None:
                    raise RuntimeError(
                        "SSH_HOST is set but sshtunnel is not installed. Install requirements."
                    )

                ssh_port = int(os.getenv("SSH_PORT", "22"))
                ssh_user = os.getenv("SSH_USER")
                ssh_password = os.getenv("SSH_PASSWORD")
                ssh_pkey = os.getenv("SSH_PKEY")

                if not ssh_user:
                    raise RuntimeError("SSH_USER is required when SSH_HOST is set.")
                if not ssh_password and not ssh_pkey:
                    raise RuntimeError(
                        "Set SSH_PASSWORD or SSH_PKEY when SSH_HOST is set."
                    )

                tunnel_kwargs = {
                    "ssh_address_or_host": (ssh_host, ssh_port),
                    "ssh_username": ssh_user,
                    "remote_bind_address": (database.DB_CONFIG["host"], database.DB_CONFIG["port"])
                }
                if ssh_pkey:
                    tunnel_kwargs["ssh_pkey"] = ssh_pkey
                if ssh_password:
                    tunnel_kwargs["ssh_password"] = ssh_password

                database.ssh_tunnel = SSHTunnelForwarder(**tunnel_kwargs)
                database.ssh_tunnel.start()
                print(f"SSH tunnel established. Local bind port: {database.ssh_tunnel.local_bind_port}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to establish SSH tunnel to {ssh_host}: {e}"
            ) from e

        conn = None
        cursor = None
        try:
            conn = mysql.connector.connect(**get_db_config())
            cursor = conn.cursor()
            cursor.execute("\""
                CREATE TABLE IF NOT EXISTS api_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    disabled BOOLEAN DEFAULT FALSE
                )
            "\"")
            conn.commit()
            print("Initialized api_users table successfully.")
        except Error as e:
            raise RuntimeError(f"Error initializing database: {e}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        yield
    finally:
        if redis_client is not None:
            await redis_client.aclose()
            redis_client = None
            print("Redis connection closed.")
        if database.ssh_tunnel:
            database.ssh_tunnel.stop()
            database.ssh_tunnel = None
            print("SSH tunnel closed.")

app = FastAPI(title="Tuloy API", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(beneficiaries.router)
