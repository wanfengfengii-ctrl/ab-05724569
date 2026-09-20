"""Pytest/Playwright 配置：真实 Chromium 访问 Compose 内的 web 与 api。"""
import os
import urllib.request

import pytest
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")
API_URL = os.environ.get("API_URL", "http://localhost:8000")


def _wait_http(url, timeout=60):
    last = None
    for _ in range(timeout * 2):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"服务在 {timeout}s 内未就绪：{url} ({last})")


@pytest.fixture(scope="session", autouse=True)
def _services_ready():
    _wait_http(API_URL + "/health")
    _wait_http(BASE_URL + "/")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api_url():
    return API_URL


@pytest.fixture()
def page():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1500, "height": 950})
        pg = context.new_page()
        pg.goto(BASE_URL, wait_until="networkidle")
        yield pg
        context.close()
        browser.close()
