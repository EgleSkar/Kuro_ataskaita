# ============================================
# NESTE - pakeisti TIKTAI close_cookies funkciją
# Sena versija ieškojo tik button elementų
# Nauja versija ieško BET KOKIO elemento su tekstu
# ============================================

# SENA (neveikianti):
# for text in ["Necessary cookies only", ...]:
#     btn = page.locator(f'button:has-text("{text}")')

# NAUJA (pakeisti į):
async def close_cookies(page):
    """Uzdaro cookies popup jei yra."""
    try:
        await page.wait_for_timeout(2000)  # Palaukiam kol popup atsiras

        # Neste naudoja OneTrust - bandome kelis selektorius
        # 1. Tiesiogiai per OneTrust ID
        onetrust = page.locator('#onetrust-reject-all-handler, #onetrust-accept-btn-handler')
        if await onetrust.count() > 0:
            await onetrust.first.click()
            print("[Neste] Cookies uzdarytas (OneTrust)")
            await page.wait_for_timeout(1000)
            return

        # 2. Per teksta - bet koks elementas (ne tik button)
        for text in ["Necessary cookies only", "Accept All Cookies", "Sutinku", "Priimti", "Reject All"]:
            btn = page.locator(f'text="{text}"')
            if await btn.count() > 0:
                await btn.first.click()
                print(f"[Neste] Cookies uzdarytas: '{text}'")
                await page.wait_for_timeout(1000)
                return

        # 3. Per role=button su tekstu
        for text in ["Necessary cookies only", "Accept All Cookies"]:
            btn = page.locator(f'[role="button"]:has-text("{text}"), a:has-text("{text}"), button:has-text("{text}"), div:has-text("{text}")')
            if await btn.count() > 0:
                await btn.first.click()
                print(f"[Neste] Cookies uzdarytas (role): '{text}'")
                await page.wait_for_timeout(1000)
                return

        print("[Neste] Cookies popup nerastas")
    except Exception as e:
        print(f"[Neste] Cookies klaida: {e}")
