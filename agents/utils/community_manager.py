import os
import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)

COOKIE_DIR = Path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "community_cookies"))
COOKIE_DIR.mkdir(parents=True, exist_ok=True)
COOKIE_FILE = COOKIE_DIR / "youtube_studio_cookies.json"

ENABLE_COMMUNITY_POSTS = os.getenv("ENABLE_COMMUNITY_POSTS", "false").lower() == "true"

POLL_TOPICS = [
    "Which AI topic should I explain next?",
    "What type of content do you prefer?",
    "How do you use AI in your daily work?",
    "What's your biggest challenge learning AI?",
    "Which tool should I review next?",
]

POLL_OPTIONS_MAP = {
    "Which AI topic should I explain next?": ["LLMs", "Computer Vision", "RL & Agents", "Edge AI"],
    "What type of content do you prefer?": ["Tutorials", "News & Updates", "Deep Dives", "Tool Reviews"],
    "How do you use AI in your daily work?": ["Coding Assistants", "Data Analysis", "Content Creation", "Not Yet"],
    "What's your biggest challenge learning AI?": ["Math & Theory", "Finding Resources", "Hands-on Practice", "Staying Updated"],
    "Which tool should I review next?": ["Cursor AI", "Claude Code", "GitHub Copilot", "Windsurf"],
}


def _playwright_available() -> bool:
    try:
        import playwright
        return True
    except ImportError:
        logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return False


async def login_to_youtube_studio(headless: bool = True, timeout_ms: int = 60000) -> object | None:
    if not _playwright_available():
        return None
    from playwright.async_api import async_playwright

    browser = None
    context = None
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=headless)

        if COOKIE_FILE.exists():
            context = await browser.new_context(
                storage_state=str(COOKIE_FILE)
            )
            page = await context.new_page()
            await page.goto("https://studio.youtube.com", timeout=timeout_ms)
            if "signin" not in page.url.lower() and "login" not in page.url.lower():
                logger.info("YouTube Studio: logged in via cookies")
                return page
            logger.info("Cookies expired, re-login needed")
            await context.close()

        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://studio.youtube.com", timeout=timeout_ms)

        logger.info("YouTube Studio: manual login required. You have 120 seconds.")
        logger.info("Please log in to your Google account in the browser window.")
        logger.info("Waiting for navigation away from signin page...")

        for _ in range(120):
            await page.wait_for_timeout(1000)
            current = page.url
            if "signin" not in current.lower() and "login" not in current.lower() and "accounts" not in current.lower():
                break

        await context.storage_state(path=str(COOKIE_FILE))
        logger.info("YouTube Studio cookies saved to %s", COOKIE_FILE)
        return page

    except Exception as e:
        logger.error("Failed to login to YouTube Studio: %s", e)
        if context:
            try:
                await context.storage_state(path=str(COOKIE_FILE))
            except Exception:
                pass
        return None
    finally:
        pass


async def create_text_post(text: str, page=None) -> bool:
    if not page:
        logger.warning("No YouTube Studio page provided")
        return False
    try:
        create_btn = page.locator("ytcp-button#create-icon").first
        if await create_btn.is_visible():
            await create_btn.click()
        else:
            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click()

        await page.wait_for_timeout(1000)

        post_option = page.get_by_role("menuitem", name="Post")
        if await post_option.is_visible():
            await post_option.click()
        else:
            logger.warning("Post option not found")
            return False

        await page.wait_for_timeout(1500)

        text_area = page.locator("div#contenteditable-textarea").first
        if not await text_area.is_visible():
            text_area = page.locator("div[contenteditable='true']").first
        await text_area.fill(text)
        await page.wait_for_timeout(500)

        post_btn = page.get_by_role("button", name="Post").last
        if await post_btn.is_visible():
            await post_btn.click()
            await page.wait_for_timeout(2000)
            logger.info("Community text post created successfully")
            return True

        logger.warning("Post button not found")
        return False

    except Exception as e:
        logger.error("Failed to create community text post: %s", e)
        return False


async def create_poll_post(question: str, options: list[str], page=None) -> bool:
    if not page:
        logger.warning("No YouTube Studio page provided")
        return False
    try:
        create_btn = page.locator("ytcp-button#create-icon").first
        if await create_btn.is_visible():
            await create_btn.click()
        else:
            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click()

        await page.wait_for_timeout(1000)

        post_option = page.get_by_role("menuitem", name="Post")
        if await post_option.is_visible():
            await post_option.click()
        else:
            logger.warning("Post option not found")
            return False

        await page.wait_for_timeout(1500)

        poll_btn = page.get_by_role("button", name="Poll")
        if await poll_btn.is_visible():
            await poll_btn.click()
        else:
            logger.warning("Poll option not found, falling back to text post")
            return await create_text_post(question, page)

        await page.wait_for_timeout(1000)

        question_area = page.locator("div#contenteditable-textarea").first
        if not await question_area.is_visible():
            question_area = page.locator("div[contenteditable='true']").first
        await question_area.fill(question)
        await page.wait_for_timeout(500)

        for i, option_text in enumerate(options[:4]):
            option_input = page.locator(f"input#poll-option-{i}").first
            if await option_input.is_visible():
                await option_input.fill(option_text)
            else:
                option_input = page.get_by_placeholder(f"Option {i + 1}").first
                if await option_input.is_visible():
                    await option_input.fill(option_text)

        await page.wait_for_timeout(500)

        post_btn = page.get_by_role("button", name="Post").last
        if await post_btn.is_visible():
            await post_btn.click()
            await page.wait_for_timeout(2000)
            logger.info("Community poll post created successfully")
            return True

        logger.warning("Post button not found")
        return False

    except Exception as e:
        logger.error("Failed to create community poll post: %s", e)
        return False


async def schedule_weekly_poll(force_topic: str | None = None, page=None) -> bool:
    if not _playwright_available():
        return False
    if page is None:
        page = await login_to_youtube_studio()
        if page is None:
            return False

    try:
        if force_topic and force_topic in POLL_OPTIONS_MAP:
            question = force_topic
        else:
            question = random.choice(POLL_TOPICS)

        options = POLL_OPTIONS_MAP.get(question, ["Yes", "No", "Maybe", "Tell me more"])
        result = await create_poll_post(question, options, page)
        await page.close()
        return result

    except Exception as e:
        logger.error("Failed to schedule weekly poll: %s", e)
        try:
            await page.close()
        except Exception:
            pass
        return False
