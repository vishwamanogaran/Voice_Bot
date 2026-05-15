from playwright.async_api import async_playwright
import asyncio


async def join_teams_meeting(meeting_url):

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False
        )

        context = await browser.new_context(
            permissions=["microphone", "camera"]
        )

        page = await context.new_page()

        await page.goto(meeting_url)

        await asyncio.sleep(10)

        print("Teams page opened")

        # login flow here

        # join flow here

        await asyncio.sleep(999999)