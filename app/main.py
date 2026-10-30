from fastapi import FastAPI
from fastapi import Request
import os
import time
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import mysql.connector
from mysql.connector import Error

from app.db import database
from app.db.database import get_db_config
from app.core.logging_config import configure_logging

try:
    from sshtunnel import SSHTunnelForwarder
except ImportError:
    SSHTunnelForwarder = None

from app.api.routes import auth, beneficiaries

logger = configure_logging()

load_dotenv(override=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(override=True)
    database.DB_CONFIG.update({
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "database": os.getenv("DB_DATABASE"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    })

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
                
                # We don't overwrite DB_CONFIG directly anymore so database.py's get_db_config handles it
                logger.info(
                    "SSH tunnel established on local port %s",
                    database.ssh_tunnel.local_bind_port,
                )
        except Exception as e:
            logger.exception("Failed to establish SSH tunnel")
            raise RuntimeError(
                f"Failed to establish SSH tunnel to {ssh_host}: {e}"
            ) from e

        conn = None
        cursor = None
        try:
            logger.info("Connecting to MySQL database")
            conn = mysql.connector.connect(**get_db_config())
            logger.info("Connected to database successfully")
            
            # NOTE: The CREATE TABLE statements have been temporarily commented out.
            # Your MySQL server is currently running a backup or has a global lock
            # (State: 'Waiting for backup lock' / 'acquiring total order isolation').
            # Trying to run any DDL (like CREATE TABLE) blocks the entire app startup.
            # Since the tables likely already exist, we can skip this and start the API normally.
            
            # cursor = conn.cursor()
            # cursor.execute('''
            #     CREATE TABLE IF NOT EXISTS api_users (
            #         id INT AUTO_INCREMENT PRIMARY KEY,
            #         username VARCHAR(255) UNIQUE NOT NULL,
            #         hashed_password VARCHAR(255) NOT NULL,
            #         disabled BOOLEAN DEFAULT FALSE
            #     )
            # ''')
            # cursor.execute('''
            #     CREATE TABLE IF NOT EXISTS `matching_transaction_CHED_tbl` ( 
            #       `id` INT UNSIGNED AUTO_INCREMENT NOT NULL,
            #       `tuloy_id` VARCHAR(100) NOT NULL COMMENT '4Ps member_id from TULOY' ,
            #       `status` VARCHAR(50) NOT NULL COMMENT 'e.g., FOUND, NOT FOUND, ERROR' ,
            #       `date_time_matched` DATETIME NULL DEFAULT CURRENT_TIMESTAMP ,
            #       `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP ,
            #        PRIMARY KEY (`id`),
            #        INDEX `idx_tuloy_id` (`tuloy_id`),
            #        INDEX `idx_status` (`status`)
            #     ) ENGINE = InnoDB;
            # ''')
            # cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
            # cursor.execute('''
            #     CREATE TABLE IF NOT EXISTS `enroll_matched_CHED_tbl` ( 
            #       `id` INT UNSIGNED AUTO_INCREMENT NOT NULL,
            #       `match_id` INT UNSIGNED NULL,
            #       `enrollment_id` INT UNSIGNED NOT NULL,
            #       `tuloy_id` VARCHAR(50) NULL COMMENT 'Unique id across agency pre-generated from TULOY' ,
            #       `member_id` INT UNSIGNED NOT NULL COMMENT 'Entry_id' ,
            #       `student_id` VARCHAR(50) NULL COMMENT 'CHED/Agency student id' ,
            #       `mm_first_name` VARCHAR(100) NULL,
            #       `mm_middle_name` VARCHAR(100) NULL,
            #       `mm_last_name` VARCHAR(100) NULL,
            #       `degree_program_name` VARCHAR(150) NULL,
            #       `degree_date_enrolled` DATE NULL,
            #       `degree_program_duration` INT NULL COMMENT 'E.g. IT - 4, Accounting - 5' ,
            #       `degree_academic_year` VARCHAR(20) NULL,
            #       `degree_year_level` INT NULL,
            #       `degree_semester` INT NULL,
            #       `enrollment_status` VARCHAR(50) NULL,
            #       `date_encoded` DATETIME NULL COMMENT 'When the record encoded to their system' ,
            #       `date_updated` DATETIME NULL COMMENT 'When the record updated to their system' ,
            #       `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ,
            #       `updated_at` TIMESTAMP NULL DEFAULT NULL  ON UPDATE CURRENT_TIMESTAMP ,
            #        PRIMARY KEY (`id`),
            #        INDEX `fk_matched_enrollment` (`enrollment_id`),
            #        INDEX `fk_matched_transaction` (`match_id`),
            #        CONSTRAINT `fk_matched_enrollment_ched` FOREIGN KEY (`enrollment_id`) REFERENCES `education_enrollment` (`enrollment_id`) ON DELETE CASCADE ON UPDATE NO ACTION,
            #        CONSTRAINT `fk_matched_transaction_ched` FOREIGN KEY (`match_id`) REFERENCES `matching_transaction_CHED_tbl` (`id`) ON DELETE SET NULL ON UPDATE NO ACTION
            #     ) ENGINE = InnoDB;
            # ''')
            # cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
            # conn.commit()
            # print("Initialized api_users, matching_transaction_CHED_tbl, and enroll_matched_CHED_tbl tables successfully.")
        except Error as e:
            logger.exception("Error initializing database connection")
            raise RuntimeError(f"Error initializing database: {e}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        logger.info("API started")
        yield
    finally:
        if database.ssh_tunnel:
            database.ssh_tunnel.stop()
            database.ssh_tunnel = None
            logger.info("SSH tunnel closed")
        logger.info("API stopped")

app = FastAPI(title="Tuloy API", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled exception for %s %s",
            request.method,
            request.url.path,
        )
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    log_method = logger.error if response.status_code >= 500 else logger.info
    log_method(
        "%s %s returned %s in %.1f ms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


app.include_router(auth.router)
app.include_router(beneficiaries.router)

if __name__ == "__main__":
    import uvicorn
    import socket

    def get_local_ip():
        try:
            # Connect to a dummy external address to find out the default local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    local_ip = "0.0.0.0"
    port = 8000
    logger.info("Starting server on http://%s:%s", local_ip, port)
    uvicorn.run("main:app", host=local_ip, port=port, reload=False)
