# pylint: disable=broad-except
"""Module to solve DKB Friendly Captcha via SeleniumBase + undetected-chromedriver"""
import logging
import os
import time
from seleniumbase import SB

logger = logging.getLogger(__name__)

FRC_INPUT_SELECTOR = 'input[name="frc-captcha-response"]'
FRC_WIDGET_SELECTOR = "iframe.frc-i-widget"
DKB_LOGIN_URL = "https://banking.dkb.de/login"
DEBUG_DIR = os.environ.get("DKB_CAPTCHA_DEBUG_DIR", "/tmp")

# The Usercentrics consent banner renders in a CROSS-ORIGIN iframe
# (web.cmp.usercentrics.eu), which is an out-of-process frame (OOPIF): its
# buttons are reachable neither via same-origin JS nor via sb.cdp.find_element()
# (main-frame target only; CDP Mode has no frame switching). Removing the iframe
# from the top frame does not work either - Usercentrics re-injects it.
# So we click the real "Ablehnen" button with a REAL OS-level GUI mouse click
# (via xvfb), which - unlike a synthetic click - reaches the OOPIF and makes
# Usercentrics persist the choice so the banner stays gone.
# Selector for the consent overlay iframe (to detect presence):
CONSENT_IFRAME_SELECTOR = 'iframe[src*="usercentrics"]'
# "Ablehnen" button center in the fixed 1280x753 headless viewport, as an offset
# from the top-left of <html> (= viewport origin in screen coords). "Alles
# akzeptieren" would be roughly (788, 537) if deny ever stops working.
CONSENT_DENY_XY = (491, 537)


def _consent_present(sb):
    """return True while the Usercentrics consent overlay iframe is in the DOM"""
    try:
        return bool(
            sb.cdp.evaluate(
                f'!!document.querySelector(\'{CONSENT_IFRAME_SELECTOR}\')'
            )
        )
    except Exception:
        return False


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
        consent_clicked = False
        consent_done = False
        settled = False
        for i in range(30):
            # First get rid of the consent banner by GUI-clicking "Ablehnen".
            # Only once the overlay iframe is gone do we touch the FRC widget -
            # otherwise the click lands on the consent overlay.
            if not consent_done:
                if _consent_present(sb):
                    try:
                        sb.cdp.gui_click_with_offset("html", *CONSENT_DENY_XY)
                        consent_clicked = True
                        logger.info(
                            "captcha: consent 'Ablehnen' gui-clicked at %s",
                            CONSENT_DENY_XY,
                        )
                    except Exception as err:
                        logger.warning("captcha: consent gui-click failed -> %r", err)
                    time.sleep(2)
                    continue  # re-check on next iteration whether it is gone
                # iframe no longer present:
                if consent_clicked:
                    logger.info("captcha: consent banner dismissed")
                elif i < 8:
                    # not rendered yet - give it a few seconds to appear
                    time.sleep(1)
                    continue
                else:
                    logger.info("captcha: no consent overlay detected")
                consent_done = True

            # Consent overlay is gone. Let the login page reflow and the FRC
            # widget initialise before clicking.
            if not settled:
                time.sleep(3)
                settled = True

            # Click the FRC "I am human" checkbox. The widget iframe is a
            # cross-origin OOPIF, so prefer a REAL mouse click (GUI, via xvfb)
            # which reliably reaches the frame; fall back to a synthetic CDP
            # click if the GUI click is unavailable.
            try:
                sb.cdp.gui_click_element(FRC_WIDGET_SELECTOR)
                logger.info("captcha: FRC widget gui-clicked")
                clicked = True
                break
            except Exception as gui_err:
                logger.debug("captcha: FRC gui-click failed: %r", gui_err)
                try:
                    sb.cdp.find_element(FRC_WIDGET_SELECTOR).click()
                    logger.info("captcha: FRC widget cdp-clicked")
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
