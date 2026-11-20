from contextlib import asynccontextmanager

from fastapi import FastAPI
from playwright.async_api import async_playwright

from app.routers import account, entries, exports, notebooks, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    # PDF 출판(섹션 3)마다 브라우저를 새로 띄우면 느려지므로, 앱 수명 동안 하나만 재사용한다.
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch()
    app.state.browser = browser
    try:
        yield
    finally:
        await browser.close()
        await playwright.stop()


app = FastAPI(title="실패작 노트 API", version="0.1.0", lifespan=lifespan)

app.include_router(entries.router)
app.include_router(notebooks.router)
app.include_router(exports.router)
app.include_router(stats.router)
app.include_router(account.router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
