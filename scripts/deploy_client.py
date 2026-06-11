#!/usr/bin/env python3
"""Create and deploy one client Telegram shop bot on Railway."""

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wizard import configure, derive_shop_name  # noqa: E402

DEFAULT_SERVICE_NAME = "bot"
DEFAULT_ENVIRONMENT = "production"


@dataclass
class CommandResult:
    args: List[str]
    stdout: str = ""
    stderr: str = ""


@dataclass
class RailwayRunner:
    dry_run: bool = False
    commands: List[List[str]] = field(default_factory=list)

    def run(
        self,
        args: List[str],
        *,
        cwd: Path,
        stdin: Optional[str] = None,
        secret_stdin: bool = False,
    ) -> CommandResult:
        self.commands.append(args)
        if self.dry_run:
            rendered = " ".join(args)
            if secret_stdin:
                rendered = f"{rendered} <secret>"
            print(f"[dry-run] {rendered}")
            return CommandResult(args=args)

        completed = subprocess.run(
            args,
            cwd=str(cwd),
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Command failed: {' '.join(args)}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        return CommandResult(args=args, stdout=completed.stdout, stderr=completed.stderr)


def copy_template(source: Path, destination: Path) -> None:
    ignored = shutil.ignore_patterns(
        ".git",
        ".railway",
        ".venv",
        ".pytest_cache",
        "__pycache__",
        "*.pyc",
        "bot_persistence.pickle",
    )
    shutil.copytree(source, destination, ignore=ignored)


def set_variable(
    runner: RailwayRunner,
    workdir: Path,
    *,
    key: str,
    value: str,
    service_name: str,
    environment: str,
    secret: bool = False,
) -> None:
    base = [
        "railway",
        "variable",
        "set",
        "--service",
        service_name,
        "--environment",
        environment,
        "--skip-deploys",
        "--json",
    ]
    if secret:
        runner.run(base + ["--stdin", key], cwd=workdir, stdin=value, secret_stdin=True)
        return

    runner.run(base + [f"{key}={value}"], cwd=workdir)


def deploy_client(
    *,
    bot_token: str,
    shop_url: str,
    project_name: str,
    service_name: str = DEFAULT_SERVICE_NAME,
    environment: str = DEFAULT_ENVIRONMENT,
    shop_name: Optional[str] = None,
    admin_handle: str = "",
    workspace: Optional[str] = None,
    skip_scrape: bool = False,
    dry_run: bool = False,
    runner: Optional[RailwayRunner] = None,
) -> RailwayRunner:
    if not bot_token:
        raise ValueError("bot_token is required")
    if not shop_url:
        raise ValueError("shop_url is required")
    if not project_name:
        raise ValueError("project_name is required")

    shop_name = shop_name or derive_shop_name(shop_url)
    runner = runner or RailwayRunner(dry_run=dry_run)

    with tempfile.TemporaryDirectory(prefix="shop-to-telegram-client-") as tempdir:
        workdir = Path(tempdir) / "app"
        copy_template(ROOT, workdir)

        configure(
            shop_url=shop_url,
            bot_token=bot_token,
            shop_name=shop_name,
            admin_handle=admin_handle,
            products_file=workdir / "products.json",
            sections_file=workdir / "sections.json",
            env_file=workdir / ".env",
            skip_scrape=skip_scrape,
        )

        runner.run(["railway", "whoami"], cwd=workdir)

        init_cmd = ["railway", "init", "--name", project_name, "--json"]
        if workspace:
            init_cmd.extend(["--workspace", workspace])
        runner.run(init_cmd, cwd=workdir)
        runner.run(["railway", "add", "--service", service_name, "--json"], cwd=workdir)

        set_variable(
            runner,
            workdir,
            key="BOT_TOKEN",
            value=bot_token,
            service_name=service_name,
            environment=environment,
            secret=True,
        )
        for key, value in {
            "SHOP_URL": shop_url,
            "SHOP_NAME": shop_name,
            "ADMIN_HANDLE": admin_handle,
        }.items():
            if value:
                set_variable(
                    runner,
                    workdir,
                    key=key,
                    value=value,
                    service_name=service_name,
                    environment=environment,
                )

        deploy_result = runner.run(
            [
                "railway",
                "up",
                "--detach",
                "--json",
                "--service",
                service_name,
                "--environment",
                environment,
                "--message",
                f"Deploy {shop_name} Telegram bot",
            ],
            cwd=workdir,
        )

        if deploy_result.stdout:
            try:
                print(json.dumps(json.loads(deploy_result.stdout), indent=2))
            except json.JSONDecodeError:
                print(deploy_result.stdout)

        print(f"Queued Railway deploy for {shop_name} ({project_name}/{service_name}).")

    return runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deploy a new client Telegram shop bot to Railway")
    parser.add_argument("--bot-token", default="", help="Telegram bot token from @BotFather")
    parser.add_argument("--shop-url", required=True, help="Client ecommerce link")
    parser.add_argument("--project-name", required=True, help="New Railway project name")
    parser.add_argument("--service-name", default=DEFAULT_SERVICE_NAME)
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--shop-name", default="", help="Display name shown in bot messages")
    parser.add_argument("--admin-handle", default="", help="Telegram username for wholesale inquiries")
    parser.add_argument("--workspace", default="", help="Railway workspace ID or exact workspace name")
    parser.add_argument("--skip-scrape", action="store_true", help="Deploy with an empty catalog")
    parser.add_argument("--dry-run", action="store_true", help="Print Railway commands without creating anything")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    bot_token = args.bot_token or os.environ.get("BOT_TOKEN") or getpass.getpass("Telegram bot token: ")
    deploy_client(
        bot_token=bot_token,
        shop_url=args.shop_url,
        project_name=args.project_name,
        service_name=args.service_name,
        environment=args.environment,
        shop_name=args.shop_name or None,
        admin_handle=args.admin_handle,
        workspace=args.workspace or None,
        skip_scrape=args.skip_scrape,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
