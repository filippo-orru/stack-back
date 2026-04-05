import logging
from typing import List, Tuple, Union
from restic_compose_backup import utils
from subprocess import Popen, PIPE, STDOUT

logger = logging.getLogger(__name__)


def test():
    return run(["ls", "/volumes"])


def ping_mysql(container_id, host, port, username, password) -> int:
    """Check if the mysql is up and can be reached"""
    return docker_exec(
        container_id,
        [
            "mysqladmin",
            "ping",
            "--host",
            host,
            "--port",
            port,
            "--user",
            username,
        ],
        environment={"MYSQL_PWD": password},
    )


def ping_mariadb(container_id, host, port, username, password) -> int:
    """Check if the mariadb is up and can be reached"""
    return docker_exec(
        container_id,
        [
            "mariadb-admin",
            "ping",
            "--host",
            host,
            "--port",
            port,
            "--user",
            username,
        ],
        environment={"MYSQL_PWD": password},
    )


def ping_postgres(container_id, host, port, username, password) -> int:
    """Check if postgres can be reached"""
    return docker_exec(
        container_id,
        [
            "pg_isready",
            f"--host={host}",
            f"--port={port}",
            f"--username={username}",
        ],
    )


def docker_exec(
    container_id: str, cmd: List[str], environment: Union[dict, list] = []
) -> int:
    """Execute a command within the given container"""
    client = utils.docker_client()
    logger.debug("docker exec inside %s: %s", container_id, " ".join(cmd))
    exit_code, (stdout, stderr) = client.containers.get(container_id).exec_run(
        cmd, demux=True, environment=environment
    )

    if stdout:
        log_std(
            "stdout",
            stdout.decode(),
            logging.DEBUG if exit_code == 0 else logging.ERROR,
        )

    if stderr:
        log_std("stderr", stderr.decode(), logging.ERROR)

    return exit_code


def run(cmd: List[str]) -> int:
    """Run a command with parameters"""
    logger.debug("cmd: %s", " ".join(cmd))
    
    # Run command and merge stderr into stdout for streaming
    child = Popen(cmd, stdout=PIPE, stderr=STDOUT, bufsize=1, universal_newlines=True)

    # Read output line by line as it is produced
    if child.stdout is None:
        logger.error("Failed to capture output from command: %s", " ".join(cmd))
        return 1

    stdout_lines = []
    for line in child.stdout:
        # Since we don't know the exit code yet, log all output at debug level.
        # This streams it in real-time.
        logger.debug(line.rstrip('\n'))
        stdout_lines.append(line)

    # Wait for the command to finish and get returncode
    child.wait()
    logger.debug("returncode %s", child.returncode)
    
    # If the command failed, log an error indicating so
    # Only do this if we're not in debug mode (since in debug mode we already logged all output)
    if child.returncode != 0:
        logger.error("Command exited with error code %s: %s", child.returncode, " ".join(cmd))
        if not logger.isEnabledFor(logging.DEBUG):
            logger.error("Command output: %s", "\n".join(stdout_lines))

    return child.returncode


def run_capture_std(cmd: List[str]) -> Tuple[str, str]:
    """Run a command with parameters and return stdout, stderr"""
    logger.debug("cmd: %s", " ".join(cmd))
    child = Popen(cmd, stdout=PIPE, stderr=PIPE)
    return child.communicate()


def log_std(source: str, data: str, level: int):
    if isinstance(data, bytes):
        data = data.decode()

    if not data.strip():
        return

    log_func = logger.debug if level == logging.DEBUG else logger.error
    log_func("%s %s %s", "-" * 10, source, "-" * 10)

    lines = data.split("\n")
    if lines[-1] == "":
        lines.pop()

    for line in lines:
        log_func(line)

    log_func("-" * 28)
