# pylint: disable=broad-except
"""Module to solve DKB Friendly Captcha via SeleniumBase + undetected-chromedriver"""
import logging
import os
import time
from seleniumbase import SB

logger = logging.getLogger(__name__)

FRC_INPUT_SELECTOR = 'input[name="frc-captcha-response"]'
DKB_LOGIN_URL = "https://banking.dkb.de/login"
DEBUG_DIR = os.environ.get("DKB_CAPTCHA_DEBUG_DIR", "/tmp")


def _dump_debug(sb, tag):
    """save a screenshot and page source for post-mortem analysis"""
    try:
        shot = os.path.join(DEBUG_DIR, f"dkb_captcha_{tag}.png")
        html = os.path.join(DEBUG_DIR, f"dkb_captcha_{tag}.html")
        sb.save_screenshot(shot)
        with open(html, "w", encoding="utf-8") as fso:
            fso.write(sb.get_page_source())
        logger.error("captcha._dump_debug(): wrote %s and %s", shot, html)
    except Exception as err:
        logger.error("captcha._dump_debug() failed: %r", err)


def _poll_frc_token(sb, timeout=30):
    """Poll the frc-captcha-response hidden input until a real token (>400 chars) appears."""
    logger.debug("captcha._poll_frc_token(): waiting for token")
    last_present = None
    last_len = 0
    for _ in range(timeout):
        try:
            last_present = sb.cdp.evaluate(
                f"!!document.querySelector('{FRC_INPUT_SELECTOR}')"
            )
            val = sb.cdp.evaluate(
                f"var e=document.querySelector('{FRC_INPUT_SELECTOR}'); e ? e.value : null"
            )
            last_len = len(val) if val else 0
            logger.debug(
                "captcha._poll_frc_token(): input_present=%s value_len=%s",
                last_present,
                last_len,
            )
            if val and last_len > 400:
                logger.debug("captcha._poll_frc_token(): got token")
                return val
        except Exception as err:
            logger.debug("captcha._poll_frc_token(): evaluate failed: %r", err)
        time.sleep(1)
    logger.error(
        "captcha._poll_frc_token(): timeout (input_present=%s last_value_len=%s)",
        last_present,
        last_len,
    )
    return False


def get_dkb_redeem_token(timeout=60, headless=False, xvfb=False):
    """Open DKB login page, solve Friendly Captcha, return the redeem_token."""
    logger.debug("captcha.get_dkb_redeem_token()")

    with SB(uc=True, locale="de", headless=headless, xvfb=xvfb) as sb:
        sb.open(DKB_LOGIN_URL)

        clicked = False
        for _ in range(30):
            # Dismiss cookie banner via CDP evaluate (works in UC/CDP mode)
            try:
                sb.cdp.evaluate(
                    "document.querySelector('#usercentrics-cmp-ui')"
                    ".shadowRoot.querySelector('button.uc-deny-button').click()"
                )
            except Exception:
                pass
            # Click the FRC iframe element via CDP (avoids cross-origin switch_to_frame)
            try:
                sb.cdp.find_element("iframe.frc-i-widget").click()
                logger.debug("captcha: FRC checkbox clicked")
                clicked = True
                break
            except Exception:
                time.sleep(1)

        if not clicked:
            logger.error("captcha: FRC widget (iframe.frc-i-widget) not found/clickable")
            _dump_debug(sb, "no-widget")

        token = _poll_frc_token(sb, timeout)

        if not token:
            _dump_debug(sb, "timeout")

    logger.debug("captcha.get_dkb_redeem_token() ended")
    return token
