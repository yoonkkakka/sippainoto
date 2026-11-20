"""노트북(권)을 PDF로 출판하는 로직.
세로쓰기(일본식 제책)를 지원해야 해서, CSS writing-mode를 온전히 렌더링할 수 있는
헤드리스 Chromium(Playwright) 기반 HTML→PDF 변환을 사용한다.
(WeasyPrint는 Windows 등 일부 환경에서 시스템 GTK/Pango 런타임이 없으면 동작하지 않아 제외)
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import Browser

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

COVER_THEMES = {
    "mono": {"label": "모노톤", "background": "#1c1c1e", "text": "#f5f5f7", "accent": "#8e8e93"},
    "lavender": {"label": "라벤더", "background": "#2d2a3d", "text": "#f1edf7", "accent": "#b9a8e0"},
    "sunset": {"label": "선셋", "background": "#3a2420", "text": "#fdf1e8", "accent": "#e08a5c"},
}
DEFAULT_THEME = "mono"


def render_notebook_html(
    notebook: dict,
    entries: list[dict],
    nickname: str,
    binding_style: str,
    cover_theme: str,
) -> str:
    template = _env.get_template("notebook.html")
    theme = COVER_THEMES.get(cover_theme, COVER_THEMES[DEFAULT_THEME])
    title_prefix = "실패작 노트" if notebook["type"] == "failure" else "감정 노트"

    return template.render(
        title=f"{title_prefix} {notebook['volume_no']}권",
        author=nickname,
        period_start=entries[0]["entry_date"] if entries else "",
        period_end=entries[-1]["entry_date"] if entries else "",
        entries=entries,
        is_vertical=(binding_style == "jp"),
        theme=theme,
    )


async def render_pdf(browser: Browser, html: str) -> bytes:
    page = await browser.new_page()
    try:
        await page.set_content(html, wait_until="load")
        return await page.pdf(format="A4", print_background=True)
    finally:
        await page.close()
