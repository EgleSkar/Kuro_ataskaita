# ============================================
# AS24 - pakeisti TIKTAI close_cookies funkciją
# Sena versija ieškojo tik button elementų
# Nauja versija ieško BET KOKIO elemento su tekstu
# AS24 naudoja Didomi consent popup
# ============================================

# SENA (neveikianti):
# for text in ["Agree and close", ...]:
#     btn = page.locator(f'button:has-text("{text}")')

# NAUJA (pakeisti į):
async def close_cookies(page):
    """Uzdaro cookies/consent popup jei yra."""
    try:
        await page.wait_for_timeout(2000)  # Palaukiam kol popup atsiras

        # 1. Didomi consent framework (AS24 naudoja Didomi)
        didomi = page.locator('#didomi-notice-agree-button, .didomi-continue-without-agreeing, [data-testid="notice-agree-button"]')
        if await didomi.count() > 0:
            await didomi.first.click()
            print("[AS24] Cookies uzdarytas (Didomi)")
            await page.wait_for_timeout(1000)
            return

        # 2. Per teksta - bet koks elementas (ne tik button)
        for text in ["Agree and close", "Continue without agreeing", "Accept all", "Accept", "Sutinku"]:
            btn = page.locator(f'text="{text}"')
            if await btn.count() > 0:
                await btn.first.click()
                print(f"[AS24] Cookies uzdarytas: '{text}'")
                await page.wait_for_timeout(1000)
                return

        # 3. Per role=button, a, div su tekstu
        for text in ["Agree and close", "Accept"]:
            btn = page.locator(f'[role="button"]:has-text("{text}"), a:has-text("{text}"), button:has-text("{text}"), span:has-text("{text}")')
            if await btn.count() > 0:
                await btn.first.click()
                print(f"[AS24] Cookies uzdarytas (role): '{text}'")
                await page.wait_for_timeout(1000)
                return

        # 4. Bandome iframe (kai kurie consent popupai yra iframe viduje)
        frames = page.frames
        for frame in frames:
            for text in ["Agree and close", "Accept"]:
                btn = frame.locator(f'text="{text}"')
                try:
                    if await btn.count() > 0:
                        await btn.first.click()
                        print(f"[AS24] Cookies uzdarytas (iframe): '{text}'")
                        await page.wait_for_timeout(1000)
                        return
                except Exception:
                    pass

        print("[AS24] Cookies popup nerastas")
    except Exception as e:
        print(f"[AS24] Cookies klaida: {e}")
