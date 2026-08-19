from __future__ import annotations

import json
import secrets
import socket
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from .coding_sheet import read_coding_sheet
from .gemini import DEFAULT_MODEL
from .manual import (
    ManualError,
    manual_from_editor_payload,
    manual_to_editor_payload,
    parse_coding_manual,
)
from .projects import (
    Project,
    ProjectError,
    create_project,
    delete_project,
    get_project,
    list_projects,
    read_manual_text,
    reset_manual_to_default,
    write_manual,
)
from .runner import Runner
from .settings import RunSettings, load_run_settings, save_run_settings
from .uploads import ProjectError as UploadProjectError  # re-export alias, same type
from .uploads import list_uploaded_pdfs, save_pdf_upload


def _embeddable_json(data: object) -> str:
    """JSON for embedding inside a <script type="application/json"> tag. Escaping
    every `<` (not just `</script>`) is the standard, always-safe way to prevent
    the string from ever being interpreted as breaking out of the tag."""

    return json.dumps(data).replace("<", "\\u003c")


PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
STATIC_DIR = PACKAGE_DIR / "static"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


class LocalSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "").split(":", 1)[0].lower()
        if host not in ALLOWED_HOSTS:
            return JSONResponse({"detail": "Invalid Host header."}, status_code=400)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin:
                host_header = request.headers.get("host", "")
                if origin.rstrip("/") not in {f"http://{host_header}", f"https://{host_header}"}:
                    return JSONResponse({"detail": "Cross-origin request rejected."}, status_code=403)
            if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
                return JSONResponse({"detail": "Cross-site request rejected."}, status_code=403)
        return await call_next(request)


class Runtime:
    def __init__(self, projects_root: Path | None = None) -> None:
        self.projects_root = projects_root
        self.session_api_key: str | None = None
        self.runner = Runner()

    def project(self, project_id: str) -> Project:
        return get_project(project_id, root=self.projects_root)


def _project_view(runtime: Runtime, project: Project) -> dict:
    """Everything the project page template needs, recomputed fresh on every
    render — including coding-sheet validation, which must reflect the CURRENT
    set of uploaded PDFs, not the set at the time the sheet was last saved."""

    manual_text = read_manual_text(project)
    manual = None
    manual_error = None
    try:
        manual = parse_coding_manual(manual_text)
    except ManualError as exc:
        manual_error = str(exc)

    # The manual is only ever edited through the structured GUI (see save_manual
    # below) — manual_editor_json seeds that editor's in-browser state. If the
    # on-disk file is somehow invalid (e.g. edited outside the app), there's
    # nothing valid to seed the editor with; the template falls back to a
    # "reset to default" recovery action instead of rendering the editor.
    manual_editor_json = _embeddable_json(manual_to_editor_payload(manual)) if manual else None

    uploaded = list_uploaded_pdfs(project.sources_dir)
    uploaded_names = {p.name for p in uploaded}

    coding_sheet = None
    if manual is not None:
        coding_sheet = read_coding_sheet(
            project.coding_sheet_path, manual=manual, uploaded_filenames=uploaded_names
        )

    run_state = runtime.runner.state(project.project_id)
    is_running = runtime.runner.is_running(project.project_id)

    orphan_pdfs = sorted(uploaded_names - {row.source_pdf for row in coding_sheet.rows}) if coding_sheet else sorted(uploaded_names)

    can_run = bool(
        runtime.session_api_key
        and manual is not None
        and coding_sheet is not None
        and coding_sheet.is_valid
        and coding_sheet.rows
        and not is_running
    )

    coded_csv = project.output_dir / "coded_data.csv"
    evidence_csv = project.output_dir / "evidence.csv"
    audit_files = sorted(project.audit_dir.glob("*.yaml")) if project.audit_dir.is_dir() else []

    return {
        "project": project,
        "manual_text": manual_text,
        "manual": manual,
        "manual_error": manual_error,
        "manual_editor_json": manual_editor_json,
        "uploaded_pdfs": uploaded,
        "coding_sheet": coding_sheet,
        "orphan_pdfs": orphan_pdfs,
        "run_state": run_state,
        "is_running": is_running,
        "can_run": can_run,
        "api_key_set": bool(runtime.session_api_key),
        "default_model": DEFAULT_MODEL,
        "has_results": coded_csv.is_file() and evidence_csv.is_file(),
        "audit_files": audit_files,
        "run_settings": load_run_settings(project),
    }


def create_app(*, token: str, projects_root: Path | None = None) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)
    app.add_middleware(LocalSecurityMiddleware)
    runtime = Runtime(projects_root=projects_root)
    app.state.runtime = runtime

    @app.get("/", include_in_schema=False)
    async def root_without_token() -> PlainTextResponse:
        return PlainTextResponse(
            "Meta-Coder is running. Use the URL printed in your terminal.", status_code=404
        )

    @app.get(f"/{token}/static/{{filename}}", include_in_schema=False)
    async def static_file(filename: str):
        path = (STATIC_DIR / filename).resolve()
        try:
            path.relative_to(STATIC_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found.")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not found.")
        return FileResponse(path)

    @app.get(f"/{token}/", response_class=HTMLResponse)
    async def home(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "home.html",
            {
                "token": token,
                "projects": list_projects(root=runtime.projects_root),
                "api_key_set": bool(runtime.session_api_key),
            },
        )

    @app.post(f"/{token}/projects")
    async def new_project(name: str = Form(...)):
        try:
            project = create_project(name, root=runtime.projects_root)
        except ProjectError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/{token}/projects/{project.project_id}", status_code=303)

    @app.post(f"/{token}/projects/{{project_id}}/delete")
    async def delete_project_route(project_id: str):
        try:
            project = runtime.project(project_id)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if runtime.runner.is_running(project_id):
            raise HTTPException(status_code=409, detail="Cancel or wait for the active run first.")
        delete_project(project)
        return RedirectResponse(f"/{token}/", status_code=303)

    @app.get(f"/{token}/projects/{{project_id}}", response_class=HTMLResponse)
    async def project_page(request: Request, project_id: str, error: str | None = None):
        try:
            project = runtime.project(project_id)
        except ProjectError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        # `error` currently only ever comes from a redirected PDF-upload failure —
        # jump the sidebar straight to that tab so the message is actually seen.
        context = {
            "token": token,
            "error": error,
            "force_tab": "sources" if error else None,
            **_project_view(runtime, project),
        }
        return TEMPLATES.TemplateResponse(request, "project.html", context)

    @app.get(f"/{token}/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "settings.html",
            {"token": token, "api_key_set": bool(runtime.session_api_key)},
        )

    @app.post(f"/{token}/settings/api-key")
    async def set_api_key(api_key: str = Form(...)):
        key = api_key.strip()
        if not key:
            raise HTTPException(status_code=400, detail="Enter a Gemini API key.")
        runtime.session_api_key = key
        return RedirectResponse(f"/{token}/settings", status_code=303)

    @app.post(f"/{token}/settings/api-key/clear")
    async def clear_api_key():
        runtime.session_api_key = None
        return RedirectResponse(f"/{token}/settings", status_code=303)

    @app.post(f"/{token}/projects/{{project_id}}/settings")
    async def save_project_settings(
        project_id: str,
        model: str = Form(DEFAULT_MODEL),
        parallel_requests: int = Form(1),
        request_delay_sec: int = Form(0),
    ):
        project = runtime.project(project_id)
        save_run_settings(
            project,
            RunSettings(model=model, parallel_requests=parallel_requests, request_delay_sec=request_delay_sec),
        )
        return RedirectResponse(f"/{token}/projects/{project_id}", status_code=303)

    @app.post(f"/{token}/projects/{{project_id}}/manual")
    async def save_manual(request: Request, project_id: str, manual_json: str = Form(...)):
        project = runtime.project(project_id)
        try:
            payload = json.loads(manual_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Malformed manual data: {exc}") from exc
        try:
            manual = manual_from_editor_payload(payload)
        except ManualError as exc:
            # Redisplay the user's just-submitted (invalid) edit, not the last
            # successfully saved manual — losing in-progress edits on a rejected
            # save would be a bad enough experience that it's worth the extra
            # context override here.
            context = {
                "token": token,
                "error": None,
                "force_tab": "manual",
                **_project_view(runtime, project),
            }
            context["manual_error"] = str(exc)
            context["manual_editor_json"] = _embeddable_json(payload)
            return TEMPLATES.TemplateResponse(request, "project.html", context, status_code=400)
        write_manual(project, manual)
        return RedirectResponse(f"/{token}/projects/{project_id}", status_code=303)

    @app.post(f"/{token}/projects/{{project_id}}/manual/reset")
    async def reset_manual(project_id: str):
        project = runtime.project(project_id)
        reset_manual_to_default(project)
        return RedirectResponse(f"/{token}/projects/{project_id}", status_code=303)

    @app.post(f"/{token}/projects/{{project_id}}/manual/import")
    async def import_manual(project_id: str, file: UploadFile = File(...)):
        # A one-time import of an existing manual.yml — e.g. one drafted from an
        # uploaded coding-manual PDF, or reused from another project — seeds the
        # structured editor. Still never hand-edited as text after this: any
        # further change goes through save_manual like everything else.
        project = runtime.project(project_id)
        raw = await file.read()
        try:
            manual = parse_coding_manual(raw.decode("utf-8", errors="replace"))
        except ManualError as exc:
            return RedirectResponse(
                f"/{token}/projects/{project_id}?error={quote(str(exc))}", status_code=303
            )
        write_manual(project, manual)
        return RedirectResponse(f"/{token}/projects/{project_id}", status_code=303)

    @app.post(f"/{token}/projects/{{project_id}}/coding-sheet")
    async def upload_coding_sheet(project_id: str, file: UploadFile = File(...)):
        project = runtime.project(project_id)
        raw = await file.read()
        project.coding_sheet_path.write_text(raw.decode("utf-8", errors="replace"), encoding="utf-8")
        return RedirectResponse(f"/{token}/projects/{project_id}", status_code=303)

    @app.post(f"/{token}/projects/{{project_id}}/uploads")
    async def upload_pdfs(project_id: str, files: list[UploadFile] = File(...)):
        project = runtime.project(project_id)
        errors = []
        for upload in files:
            try:
                save_pdf_upload(project.sources_dir, upload.filename or "", upload.file)
            except UploadProjectError as exc:
                errors.append(str(exc))
        if errors:
            return RedirectResponse(
                f"/{token}/projects/{project_id}?error={quote('; '.join(errors))}", status_code=303
            )
        return RedirectResponse(f"/{token}/projects/{project_id}", status_code=303)

    @app.post(f"/{token}/projects/{{project_id}}/uploads/delete")
    async def delete_pdf(project_id: str, filename: str = Form(...)):
        project = runtime.project(project_id)
        safe = Path(filename).name
        target = project.sources_dir / safe
        if target.is_file() and target.suffix.lower() == ".pdf":
            target.unlink()
        return RedirectResponse(f"/{token}/projects/{project_id}", status_code=303)

    @app.post(f"/{token}/projects/{{project_id}}/run")
    async def start_run(project_id: str):
        project = runtime.project(project_id)
        view = _project_view(runtime, project)
        if not view["can_run"]:
            reasons = []
            if not runtime.session_api_key:
                reasons.append("a Gemini API key is required (set it in Settings)")
            if view["manual_error"]:
                reasons.append("the coding manual has a validation error")
            if view["coding_sheet"] is None or not view["coding_sheet"].is_valid:
                reasons.append("the coding sheet has validation errors")
            if view["coding_sheet"] is not None and not view["coding_sheet"].rows:
                reasons.append("the coding sheet has no rows")
            if runtime.runner.is_running(project_id):
                reasons.append("a run is already in progress")
            raise HTTPException(status_code=400, detail="Cannot run: " + "; ".join(reasons) + ".")

        settings = view["run_settings"]
        runtime.runner.start(
            project=project,
            manual=view["manual"],
            coding_sheet=view["coding_sheet"],
            api_key=runtime.session_api_key,
            model=settings.model,
            parallel_requests=settings.parallel_requests,
            request_delay_sec=settings.request_delay_sec,
        )
        return RedirectResponse(f"/{token}/projects/{project_id}", status_code=303)

    @app.get(f"/{token}/projects/{{project_id}}/status")
    async def run_status(project_id: str):
        runtime.project(project_id)
        state = runtime.runner.state(project_id)
        if state is None:
            return {"status": "idle"}
        return state.snapshot()

    @app.get(f"/{token}/projects/{{project_id}}/download/coded")
    async def download_coded(project_id: str):
        project = runtime.project(project_id)
        path = project.output_dir / "coded_data.csv"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="No results yet.")
        return FileResponse(path, media_type="text/csv", filename=f"{project.name}-coded_data.csv")

    @app.get(f"/{token}/projects/{{project_id}}/download/evidence")
    async def download_evidence(project_id: str):
        project = runtime.project(project_id)
        path = project.output_dir / "evidence.csv"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="No results yet.")
        return FileResponse(path, media_type="text/csv", filename=f"{project.name}-evidence.csv")

    @app.get(f"/{token}/projects/{{project_id}}/audit/{{filename}}")
    async def view_audit(project_id: str, filename: str):
        project = runtime.project(project_id)
        safe = Path(filename).name
        path = (project.audit_dir / safe).resolve()
        try:
            path.relative_to(project.audit_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found.")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not found.")
        # text/plain (not a YAML MIME type) so it renders inline in the browser for
        # quick auditing, rather than forcing a download.
        return FileResponse(path, media_type="text/plain")

    return app


def launch_web(*, open_browser: bool = True, port: int | None = None) -> int:
    token = secrets.token_urlsafe(32)
    if port is None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
    app = create_app(token=token)
    url = f"http://127.0.0.1:{port}/{token}/"
    print(f"Meta-Coder is running locally at {url}")
    print("Press Ctrl+C to stop it.")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    return 0
