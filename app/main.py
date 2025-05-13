import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from typing import Literal

import jinja_partials
from fastapi import Depends
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from starlette.templating import _TemplateResponse


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    PROJECT_NAME: str = "Public Quantum Network"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
SettingsDep = Annotated[Settings, Depends(get_settings)]

app = FastAPI(
    title=settings.PROJECT_NAME,
)
app.mount("/static", StaticFiles(directory=f"{Path(__file__).parent}/static"), name="static")


@lru_cache
def get_templates() -> Jinja2Templates:
    return Jinja2Templates(directory=f"{Path(__file__).parent}/templates")


templates = get_templates()
TemplatesDep = Annotated[Jinja2Templates, Depends(get_templates)]
jinja_partials.register_starlette_extensions(templates)


@app.get("/", response_class=HTMLResponse)
def root(request: Request, templates: TemplatesDep, settings: SettingsDep) -> _TemplateResponse:
    ctx = {"protocols": ["chsh", "qkd", "qpv"]}
    return templates.TemplateResponse(request=request, name="home/index.html", context=ctx)


@app.get("/protocols/{name}", response_class=HTMLResponse)
def protocol(name: str, request: Request, templates: TemplatesDep, settings: SettingsDep) -> _TemplateResponse:
    ctx = {"protocol_name": name, "description": f"a description of the {name} protocol"}
    return templates.TemplateResponse(request=request, name="home/protocols.html", context=ctx)


# app.include_router(api_router, prefix=settings.API_V1_STR)
# app.include_router(view_router)
