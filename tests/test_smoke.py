"""Playwright smoke: verify multi-turma UI + delta computation."""
import sys

from playwright.sync_api import sync_playwright


BASE = "http://127.0.0.1:8765"


def main() -> int:
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 950})
        page = ctx.new_page()
        page.goto(BASE, wait_until="networkidle")

        health = page.locator("#health-line").text_content(timeout=5000)
        print("Health:", health)
        if "12 grades" not in health:
            failures.append(f"health line mismatch: {health}")

        # Turmas populated (bootstrap should have run OR previous state)
        rows = page.locator(".turma-row")
        print("Turma rows:", rows.count())

        # Bootstrap: force replace
        page.on("dialog", lambda d: d.accept())
        page.click("#bootstrap-btn")
        page.wait_for_timeout(2500)
        rows = page.locator(".turma-row")
        row_count = rows.count()
        print("After bootstrap:", row_count, "turma rows")
        if row_count != 13:
            failures.append(f"expected 13 turmas after bootstrap, got {row_count}")

        # Search PDS II
        page.fill("#search", "projeto e desenvolvimento de sistema ii")
        page.wait_for_timeout(400)
        cards = page.locator(".card")
        print("PDS II cards:", cards.count())
        exclusive = page.locator(".card-badge.exclusive").first
        if exclusive.count() == 0:
            failures.append("PDS II missing exclusive badge")

        # Delta chip for Turma 2023 = +2
        chip = page.locator(".turma-delta-chip.positive.next").first
        if chip.count() == 0:
            failures.append("expected next positive delta chip for PDS II Turma 2023")
        else:
            print("PDS II chip:", chip.text_content())

        # Search Sistemas Operacionais → EGS 2000 M10 should have "agora" chip (T2024)
        page.fill("#search", "sistemas operacionais")
        page.wait_for_timeout(400)
        now_chips = page.locator(".turma-delta-chip.zero")
        print("Sistemas Operacionais 'agora' chips:", now_chips.count())
        if now_chips.count() < 1:
            failures.append("expected 'agora' chip on SO / EGS 2000 M10")

        # Detail modal
        page.locator(".card").first.click()
        page.wait_for_selector("#detail-modal:not(.hidden)", timeout=3000)
        title = page.locator("#detail-modal h1").text_content()
        print("Modal:", title)
        page.keyboard.press("Escape")
        page.wait_for_selector("#detail-modal", state="hidden")

        # Timeline
        page.click('.tab[data-view="timeline"]')
        page.wait_for_selector("#view-timeline.active")
        tl_rows = page.locator("#timeline-body tr").count()
        print("Timeline rows:", tl_rows)
        if tl_rows != 12:
            failures.append(f"timeline expected 12 rows, got {tl_rows}")

        # Turma tags in current cells
        tags = page.locator(".turma-tag").count()
        print("Turma tags in timeline:", tags)
        if tags < 5:
            failures.append(f"expected multiple turma-tag markers, got {tags}")

        browser.close()

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
