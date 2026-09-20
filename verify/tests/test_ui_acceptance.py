"""Browser-driven acceptance tests covering the full web <-> API integration."""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import expect, sync_playwright

WEB_BASE = os.environ.get("WEB_BASE", "http://web")


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        # Standard flags for running Chromium inside a container.
        b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    page = browser.new_page()
    yield page
    page.close()


def test_workbench_loads(page):
    page.goto(WEB_BASE)
    expect(page).to_have_title("多波长激光干涉仪 · 整周数解算工作台")
    expect(page.get_by_test_id("solve-button")).to_be_visible()
    expect(page.get_by_test_id("range-lo")).to_have_value("0")
    expect(page.get_by_test_id("range-hi")).to_have_value("4")


def test_unique_solution_flow(page):
    page.goto(WEB_BASE)
    # Default inputs are the unique-solution example.
    page.get_by_test_id("solve-button").click()
    banner = page.get_by_test_id("status-banner")
    expect(banner).to_contain_text("唯一解")
    witness = page.get_by_test_id("witness-0")
    expect(witness).to_contain_text("9/10")
    expect(witness).to_contain_text("21/20")
    expect(witness).to_contain_text("n1=0")
    expect(witness).to_contain_text("n2=0")
    # Residual intervals and common band are shown.
    expect(witness).to_contain_text("共同距离带")
    expect(witness).to_contain_text("残差区间")
    expect(page.get_by_test_id("result-meta")).to_contain_text("可能性类别总数 1")


def test_multiple_solution_flow(page):
    page.goto(WEB_BASE)
    page.get_by_test_id("preset-multiple").click()
    page.get_by_test_id("solve-button").click()
    banner = page.get_by_test_id("status-banner")
    expect(banner).to_contain_text("多解")
    expect(banner).to_contain_text("共 2 类")
    first = page.get_by_test_id("witness-0")
    second = page.get_by_test_id("witness-1")
    expect(first).to_contain_text("4/5")
    expect(first).to_contain_text("n1=0")
    expect(second).to_contain_text("141/20")
    expect(second).to_contain_text("n1=3")
    expect(second).to_contain_text("n2=2")


def test_no_solution_flow(page):
    page.goto(WEB_BASE)
    page.get_by_test_id("preset-none").click()
    page.get_by_test_id("solve-button").click()
    expect(page.get_by_test_id("status-banner")).to_contain_text("无解")
    expect(page.get_by_test_id("witness-0")).to_have_count(0)


def test_long_range_flow(page):
    page.goto(WEB_BASE)
    page.get_by_test_id("preset-long-range").click()
    page.get_by_test_id("solve-button").click()
    expect(page.get_by_test_id("status-banner")).to_contain_text("多解")
    expect(page.get_by_test_id("result-meta")).to_contain_text("周期合并")
    expect(page.get_by_test_id("result-meta")).to_contain_text("40961")


def test_input_change_clears_previous_result(page):
    page.goto(WEB_BASE)
    page.get_by_test_id("solve-button").click()
    expect(page.get_by_test_id("status-banner")).to_be_visible()
    # Any edit invalidates the previous conclusion.
    page.get_by_test_id("input-wavelength-0").fill("2.5")
    expect(page.get_by_test_id("status-banner")).to_have_count(0)
    expect(page.get_by_test_id("result")).to_have_count(0)


def test_import_json_flow(page):
    page.goto(WEB_BASE)
    page.get_by_test_id("import-toggle").click()
    page.get_by_test_id("import-textarea").fill(
        '{"range": {"lo": "0", "hi": "10"}, "channels": ['
        '{"wavelength": "2", "phase": "0.5", "epsilon": "0.1"},'
        '{"wavelength": "3", "phase": "0.25", "epsilon": "0.1"}]}'
    )
    page.get_by_test_id("import-apply").click()
    expect(page.get_by_test_id("range-hi")).to_have_value("10")
    expect(page.get_by_test_id("input-phase-1")).to_have_value("0.25")
    page.get_by_test_id("solve-button").click()
    expect(page.get_by_test_id("status-banner")).to_contain_text("多解")


def test_invalid_input_blocks_solve(page):
    page.goto(WEB_BASE)
    page.get_by_test_id("input-epsilon-0").fill("0.25")
    expect(page.get_by_test_id("validation-errors")).to_contain_text("误差界")
    expect(page.get_by_test_id("solve-button")).to_be_disabled()


def test_add_and_remove_channel(page):
    page.goto(WEB_BASE)
    page.get_by_test_id("add-channel").click()
    expect(page.get_by_test_id("channel-row-2")).to_be_visible()
    page.get_by_test_id("remove-channel-2").click()
    expect(page.get_by_test_id("channel-row-2")).to_have_count(0)
