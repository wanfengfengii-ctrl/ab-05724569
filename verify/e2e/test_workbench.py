"""真实浏览器端到端验收：覆盖唯一/多解/无解、整周与残差展示、
长距离非枚举、输入失效、校验阻断、JSON 导入与真实 API 联通。"""
import json
import urllib.request


def test_page_loads_and_api_online(page):
    assert "整周解算工作台" in page.title()
    page.wait_for_selector('[data-testid="health"].health-ok', timeout=15000)
    page.wait_for_selector('[data-testid="solve-btn"]')


def test_unique_scenario_default(page):
    page.click('[data-testid="solve-btn"]')
    page.wait_for_selector(".verdict.unique")
    assert "唯一可行整周向量" in page.locator(".verdict-title").inner_text()

    # 精确距离交集：[1/4, 7/20]
    band = page.locator(".witness .band-values").first
    band_text = band.inner_text()
    assert "1/4" in band_text and "7/20" in band_text

    # 每路整周数均为 0，逐路复核通过
    orders = page.locator(".witness tbody td.order").all_inner_texts()
    assert orders == ["0", "0"]
    assert page.locator('.witness .badge:has-text("逐路复核通过")').count() == 1
    assert page.locator('.witness tbody .badge.ok:has-text("满足")').count() == 2

    # 残差区间两行均存在且包含分数
    residuals = page.locator(".witness tbody td", has_text=";").all_inner_texts()
    assert len(residuals) == 2


def test_multiple_scenario_two_witnesses_sorted(page):
    page.select_option(".example-pick select", label="多解（粗测重合，返回前两份见证）")
    page.click('[data-testid="solve-btn"]')
    page.wait_for_selector(".verdict.multiple")
    title = page.locator(".verdict-title").inner_text()
    assert "4" in title

    cards = page.locator(".witness")
    assert cards.count() == 2
    assert "候选见证 #1" in cards.nth(0).inner_text()
    assert "候选见证 #2" in cards.nth(1).inner_text()

    o1 = cards.nth(0).locator("td.order").all_inner_texts()
    o2 = cards.nth(1).locator("td.order").all_inner_texts()
    assert o1 == ["0", "0"]
    assert o2 == ["1", "1"]
    assert "前两份见证" in page.locator(".more-hint").inner_text()


def test_infeasible_scenario_verdict(page):
    page.select_option(".example-pick select", label="无解（相位互斥，明确裁决）")
    page.click('[data-testid="solve-btn"]')
    page.wait_for_selector(".verdict.infeasible")
    assert "无解" in page.locator(".verdict-title").inner_text()
    assert page.locator(".witness").count() == 0
    assert page.locator(".infeasible-box").count() == 1


def test_long_range_unique_and_non_enumeration(page):
    page.select_option(".example-pick select", label="长距离三路激光（41 km，禁止枚举最短波长）")
    page.click('[data-testid="solve-btn"]')
    page.wait_for_selector(".verdict.unique")

    text = page.locator(".results").inner_text()
    assert "41234.7499" in text and "41234.7500" in text
    # 整周数达到数千万，证明后端确实解析了长距离真实问题
    assert "65,141,785" in text

    stats = page.locator(".stats").inner_text().replace(",", "")
    # 细化分支数远小于最短波长全枚举数（对照数字都展示给计量员）
    assert "19920" in stats  # 朴素枚举 19,920
    assert "实际细化分支：31" in stats


def test_input_change_invalidates_old_conclusion(page):
    page.click('[data-testid="solve-btn"]')
    page.wait_for_selector(".verdict.unique")

    # 修改任意输入：旧结论必须立即消失，不允许保留
    page.fill('[data-testid="distance-max"]', "1.3")
    body = page.locator('[data-testid="results"]').inner_text()
    assert "尚未解算" in body
    assert page.locator(".verdict").count() == 0


def test_invalid_input_blocks_solve(page):
    page.fill('input[aria-label="第 1 路相位"]', "1.5")
    page.wait_for_selector('[data-testid="client-errors"]')
    errors = page.locator('[data-testid="client-errors"]').inner_text()
    assert "相位必须位于 [0, 1)" in errors
    assert page.is_disabled('[data-testid="solve-btn"]')


def test_quarter_cycle_boundary_rejected(page):
    page.fill('input[aria-label="第 1 路误差界"]', "0.25")
    page.wait_for_selector('[data-testid="client-errors"]')
    assert "1/4" in page.locator('[data-testid="client-errors"]').inner_text()
    assert page.is_disabled('[data-testid="solve-btn"]')


def test_add_and_remove_channels_bounds(page):
    # 默认 2 路；增加到 3 路后解算仍可用
    page.click('button:has-text("增加一路")')
    rows = page.locator(".channel-table tbody tr:not(.error-row)")
    assert rows.count() == 3
    page.locator('.channel-table button:has-text("删除")').first.click()
    assert page.locator(".channel-table tbody tr:not(.error-row)").count() == 2
    # 仅剩 2 路时删除按钮禁用
    assert page.is_disabled('.channel-table button:has-text("删除")')


def test_import_json_then_solve(page):
    payload = {
        "distance": {"min": "0", "max": "3"},
        "channels": [
            {"wavelength": "1", "phase": "0.25", "epsilon": "0.1"},
            {"wavelength": "1", "phase": "0.8", "epsilon": "0.1"},
        ],
    }
    page.click('button:has-text("导入 JSON")')
    page.fill(".modal textarea", json.dumps(payload))
    page.click('.modal-actions button:has-text("导入粘贴内容")')
    page.wait_for_selector(".modal", state="detached")
    assert page.input_value('[data-testid="distance-max"]') == "3"
    page.click('[data-testid="solve-btn"]')
    page.wait_for_selector(".verdict.infeasible")


def test_browser_calls_real_api_and_matches(page, api_url):
    # 在浏览器页面上下文里直接 fetch 真实后端，证明前后端通过 HTTP 联通。
    result = page.evaluate(
        """async (url) => {
            const r = await fetch(url + '/api/solve', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    distance: {min: '41230', max: '41240'},
                    channels: [
                        {wavelength: '0.000633', phase: '0.150078988941548', epsilon: '0.000002'},
                        {wavelength: '0.000532', phase: '0.571428571428571', epsilon: '0.000002'},
                        {wavelength: '0.000502', phase: '0.254980079681275', epsilon: '0.000002'}
                    ]
                })
            });
            return {status: r.status, body: await r.json()};
        }""",
        api_url,
    )
    assert result["status"] == 200
    body = result["body"]
    assert body["status"] == "unique"
    assert body["witnesses"][0]["orders"] == [65141785, 77508928, 82140936]
    assert body["witnesses"][0]["distance_band"]["lower"]["decimal"].startswith(
        "41234.7499"
    )
    assert body["witnesses"][0]["distance_band"]["upper"]["decimal"].startswith(
        "41234.7500"
    )
    # 实际细化分支远少于最短波长全枚举数（31 vs 19,920）
    assert body["stats"]["cells_refined"] < body["stats"]["naive_shortest_wavelength_integers"] // 100


def test_api_health_directly(api_url):
    with urllib.request.urlopen(api_url + "/health", timeout=5) as resp:
        assert resp.status == 200
        assert json.loads(resp.read())["status"] == "ok"
