import json
from pathlib import Path

from scripts.deploy_client import RailwayRunner, deploy_client


def test_dry_run_deploy_plans_railway_project_service_variables_and_upload():
    runner = RailwayRunner(dry_run=True)

    deploy_client(
        bot_token="123:secret",
        shop_url="https://shop.example",
        project_name="shop-example-bot",
        service_name="bot",
        shop_name="Shop Example",
        admin_handle="@merchant",
        skip_scrape=True,
        runner=runner,
    )

    commands = [" ".join(command) for command in runner.commands]

    assert commands[0] == "railway whoami"
    assert "railway init --name shop-example-bot --json" in commands
    assert "railway add --service bot --json" in commands
    assert any("railway variable set --service bot --environment production --skip-deploys --json --stdin BOT_TOKEN" == command for command in commands)
    assert any(command.endswith("SHOP_URL=https://shop.example") for command in commands)
    assert any(command.endswith("SHOP_NAME=Shop Example") for command in commands)
    assert any(command.startswith("railway up --detach --json --service bot --environment production") for command in commands)
    assert all("123:secret" not in command for command in commands)


def test_railway_config_runs_single_always_on_worker():
    config = json.loads(Path("railway.json").read_text())

    assert config["build"]["builder"] == "RAILPACK"
    assert config["deploy"]["startCommand"] == "python bot.py"
    assert config["deploy"]["numReplicas"] == 1
    assert config["deploy"]["sleepApplication"] is False
    assert config["deploy"]["restartPolicyType"] == "ALWAYS"
    assert config["deploy"]["overlapSeconds"] == 0
