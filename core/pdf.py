"""
Génération PDF HTML → PDF via Playwright (Chromium),
même approche et qualité que WeddingPlanner.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def get_playwright_browsers_path() -> str:
    path = getattr(settings, 'PLAYWRIGHT_BROWSERS_PATH', None)
    if not path:
        path = Path(settings.BASE_DIR) / '.playwright-browsers'
    return str(path)


def _ensure_playwright_env() -> None:
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', get_playwright_browsers_path())


def _launch_chromium(playwright):
    """Lance Chromium comme WeddingPlanner (bundled → chrome → msedge)."""
    _ensure_playwright_env()
    attempts = [
        ('bundled', lambda: playwright.chromium.launch(headless=True)),
        ('chrome', lambda: playwright.chromium.launch(headless=True, channel='chrome')),
        ('msedge', lambda: playwright.chromium.launch(headless=True, channel='msedge')),
    ]
    errors = []
    for label, launcher in attempts:
        try:
            return launcher()
        except Exception as exc:
            errors.append(f'{label}: {exc}')
            logger.warning('Playwright launch failed (%s): %s', label, exc)
    raise RuntimeError(
        'Impossible de lancer Chromium pour le PDF. '
        f'Détails : {" | ".join(errors)}. '
        'Exécutez : python -m playwright install chromium '
        f'(navigateurs attendus dans {get_playwright_browsers_path()})'
    )


def html_to_pdf(html: str, base_url: str | None = None) -> bytes | None:
    """
    Rend un HTML en PDF A4 haute qualité (print_background), via Playwright.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            'Playwright non installé. pip install playwright && python -m playwright install chromium'
        )
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        with sync_playwright() as playwright:
            browser = _launch_chromium(playwright)
            try:
                page = browser.new_page(viewport={'width': 794, 'height': 1123})
                # networkidle : même qualité de rendu que WeddingPlanner
                page.set_content(html, wait_until='networkidle')
                page.pdf(
                    path=tmp_path,
                    format='A4',
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={
                        'top': '0',
                        'right': '0',
                        'bottom': '0',
                        'left': '0',
                    },
                )
            finally:
                browser.close()

        path = Path(tmp_path)
        if path.is_file() and path.stat().st_size > 0:
            return path.read_bytes()
        logger.error('PDF Playwright vide ou manquant')
        return None
    except Exception as exc:
        logger.exception('Erreur génération PDF Playwright: %s', exc)
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
