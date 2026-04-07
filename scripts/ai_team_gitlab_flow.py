#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_INFO = ROOT / "docs/test-info.md"
DEFAULT_SECRET_INFO = Path("~/.config/kernel-sense/test-info.local.md").expanduser()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drive GitLab MR/reviewer flow for unattended ai-team delivery.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--doc-info", default=str(DEFAULT_DOC_INFO))
    parser.add_argument("--secret-info")
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_cmd = subparsers.add_parser("discover")
    discover_cmd.add_argument("--json", action="store_true")

    create_cmd = subparsers.add_parser("create-project")
    create_cmd.add_argument("--project-name")
    create_cmd.add_argument("--project-path")
    create_cmd.add_argument("--namespace-id")
    create_cmd.add_argument("--visibility", default="private")
    create_cmd.add_argument("--write-report")
    create_cmd.add_argument("--json", action="store_true")

    plan_cmd = subparsers.add_parser("plan-mr")
    plan_cmd.add_argument("--source-branch")
    plan_cmd.add_argument("--target-branch")
    plan_cmd.add_argument("--title")
    plan_cmd.add_argument("--description")
    plan_cmd.add_argument("--remove-source-branch", action="store_true")
    plan_cmd.add_argument("--draft", action="store_true")
    plan_cmd.add_argument("--write-report")
    plan_cmd.add_argument("--json", action="store_true")

    ensure_cmd = subparsers.add_parser("ensure-mr")
    ensure_cmd.add_argument("--source-branch")
    ensure_cmd.add_argument("--target-branch")
    ensure_cmd.add_argument("--title")
    ensure_cmd.add_argument("--description")
    ensure_cmd.add_argument("--remove-source-branch", action="store_true")
    ensure_cmd.add_argument("--draft", action="store_true")
    ensure_cmd.add_argument("--write-report")
    ensure_cmd.add_argument("--json", action="store_true")

    status_cmd = subparsers.add_parser("mr-status")
    status_cmd.add_argument("--source-branch")
    status_cmd.add_argument("--target-branch")
    status_cmd.add_argument("--write-report")
    status_cmd.add_argument("--json", action="store_true")

    pipeline_cmd = subparsers.add_parser("pipeline-status")
    pipeline_cmd.add_argument("--ref")
    pipeline_cmd.add_argument("--pipeline-id", type=int)
    pipeline_cmd.add_argument("--write-report")
    pipeline_cmd.add_argument("--json", action="store_true")

    note_cmd = subparsers.add_parser("mr-note")
    note_cmd.add_argument("--mr-iid", type=int)
    note_cmd.add_argument("--source-branch")
    note_cmd.add_argument("--target-branch")
    note_cmd.add_argument("--body")
    note_cmd.add_argument("--body-file")
    note_cmd.add_argument("--write-report")
    note_cmd.add_argument("--json", action="store_true")

    return parser.parse_args()


def resolve_repo(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=check)


def git_output(repo: Path, *args: str) -> str:
    result = run_git(repo, *args, check=False)
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def load_info_file(path: Optional[Path]) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            values[key] = value
    return values


def load_runtime_config(doc_info: Path, secret_info: Optional[Path]) -> dict[str, str]:
    values: dict[str, str] = {}
    values.update(load_info_file(doc_info))
    values.update(load_info_file(secret_info))
    for key, value in os.environ.items():
        if key.startswith("GITLAB_"):
            values[key] = value
    return values


def default_secret_info() -> Optional[Path]:
    return DEFAULT_SECRET_INFO if DEFAULT_SECRET_INFO.exists() else None


def current_branch(repo: Path) -> str:
    return git_output(repo, "branch", "--show-current")


def default_target_branch(repo: Path) -> str:
    head = git_output(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
    if head.startswith("refs/remotes/origin/"):
        return head.rsplit("/", 1)[-1]
    remote_show = git_output(repo, "remote", "show", "origin")
    for line in remote_show.splitlines():
        text = line.strip()
        if text.startswith("HEAD branch:"):
            return text.split(":", 1)[1].strip()
    return "main"


def infer_project_path(repo: Path, config: dict[str, str]) -> str:
    explicit = (config.get("GITLAB_PROJECT_PATH") or "").strip()
    if explicit:
        return explicit
    remote_url = git_output(repo, "remote", "get-url", "origin")
    if not remote_url:
        return ""
    trimmed = remote_url.split("://", 1)[-1]
    path = trimmed.split("/", 1)[-1]
    if path.endswith(".git"):
        path = path[:-4]
    return path


def gitlab_base_url(config: dict[str, str]) -> str:
    explicit = (config.get("GITLAB_BASE_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    host = (config.get("GITLAB_HOST") or "").strip()
    port = (config.get("GITLAB_PORT") or "").strip() or "80"
    if not host:
        return ""
    return f"http://{host}:{port}".rstrip("/")


def project_api_path(project_path: str) -> str:
    return urllib.parse.quote(project_path, safe="")


def request_json(method: str, url: str, token: str, payload: Optional[dict[str, Any]] = None) -> Any:
    data = None
    headers = {"PRIVATE-TOKEN": token}
    if payload is not None:
        data = urllib.parse.urlencode(payload, doseq=True).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def api_get(base_url: str, token: str, api_path: str, query: Optional[dict[str, Any]] = None) -> Any:
    suffix = f"?{urllib.parse.urlencode(query, doseq=True)}" if query else ""
    return request_json("GET", f"{base_url}{api_path}{suffix}", token)


def api_post(base_url: str, token: str, api_path: str, payload: Optional[dict[str, Any]] = None) -> Any:
    return request_json("POST", f"{base_url}{api_path}", token, payload)


def api_get_optional(base_url: str, token: str, api_path: str, query: Optional[dict[str, Any]] = None) -> Any:
    try:
        return api_get(base_url, token, api_path, query)
    except Exception:
        return {}


def discover(repo: Path, config: dict[str, str]) -> dict[str, Any]:
    return {
        "status": "ok",
        "repo": str(repo),
        "gitlab_base_url": gitlab_base_url(config),
        "project_path": infer_project_path(repo, config),
        "project_id": (config.get("GITLAB_PROJECT_ID") or "").strip(),
        "source_branch": current_branch(repo),
        "target_branch": default_target_branch(repo),
        "token_present": bool((config.get("GITLAB_TOKEN") or "").strip()),
        "autodispatch_label": (config.get("GITLAB_AUTODISPATCH_LABEL") or "").strip(),
    }


def clean_project_name(value: str) -> str:
    raw = " ".join(value.replace("_", " ").replace("-", " ").split()).strip()
    return raw or "ai-team-standalone"


def clean_project_path(value: str) -> str:
    text = value.strip().strip("/")
    if not text:
        return "ai-team-standalone"
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    normalized = []
    for char in text.lower():
        if char.isalnum() or char in {"-", "_", "."}:
            normalized.append(char)
        elif char in {" ", "/"}:
            normalized.append("-")
    cleaned = "".join(normalized).strip("-.")
    return cleaned or "ai-team-standalone"


def infer_project_creation_inputs(
    config: dict[str, str],
    *,
    project_name: Optional[str],
    project_path: Optional[str],
) -> tuple[str, str, str]:
    configured_project_path = str(config.get("GITLAB_PROJECT_PATH") or "").strip()
    configured_namespace = configured_project_path.rsplit("/", 1)[0] if "/" in configured_project_path else ""
    raw_path = (project_path or "").strip()
    raw_name = (project_name or "").strip()
    namespace_path = configured_namespace
    if raw_path and "/" in raw_path:
        namespace_path = raw_path.rsplit("/", 1)[0].strip()
    resolved_path = clean_project_path(raw_path or raw_name or "ai-team-standalone")
    resolved_name = clean_project_name(raw_name or resolved_path)
    return resolved_name, resolved_path, namespace_path


def authenticated_remote_url(remote_url: str, token: str, username: str = "oauth2") -> str:
    if not remote_url or not token:
        return remote_url
    parsed = urllib.parse.urlparse(remote_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return remote_url
    netloc = f"{urllib.parse.quote(username, safe='')}:{urllib.parse.quote(token, safe='')}@{parsed.netloc}"
    return urllib.parse.urlunparse(parsed._replace(netloc=netloc))


def ensure_project(
    repo: Path,
    config: dict[str, str],
    *,
    project_name: Optional[str],
    project_path: Optional[str],
    namespace_id: Optional[str],
    visibility: str,
) -> dict[str, Any]:
    token = (config.get("GITLAB_TOKEN") or "").strip()
    base_url = gitlab_base_url(config)
    if not token or not base_url:
        raise RuntimeError("missing gitlab context")

    resolved_name, resolved_path, namespace_path = infer_project_creation_inputs(
        config,
        project_name=project_name,
        project_path=project_path,
    )
    effective_project_path = f"{namespace_path}/{resolved_path}" if namespace_path else resolved_path
    encoded_project = project_api_path(effective_project_path)

    existing = api_get_optional(base_url, token, f"/api/v4/projects/{encoded_project}")
    if isinstance(existing, dict) and existing.get("id"):
        return {
            "status": "existing",
            "project_id": existing.get("id"),
            "project_name": existing.get("name") or resolved_name,
            "project_path": existing.get("path_with_namespace") or effective_project_path,
            "namespace_path": namespace_path,
            "web_url": existing.get("web_url"),
            "http_url_to_repo": existing.get("http_url_to_repo"),
            "ssh_url_to_repo": existing.get("ssh_url_to_repo"),
            "repo": str(repo),
        }

    payload: dict[str, Any] = {
        "name": resolved_name,
        "path": resolved_path,
        "visibility": visibility,
    }
    if namespace_id:
        payload["namespace_id"] = str(namespace_id).strip()
    created = api_post(base_url, token, "/api/v4/projects", payload)
    if not isinstance(created, dict) or not created.get("id"):
        raise RuntimeError("gitlab project creation failed")
    return {
        "status": "created",
        "project_id": created.get("id"),
        "project_name": created.get("name") or resolved_name,
        "project_path": created.get("path_with_namespace") or effective_project_path,
        "namespace_path": namespace_path,
        "web_url": created.get("web_url"),
        "http_url_to_repo": created.get("http_url_to_repo"),
        "ssh_url_to_repo": created.get("ssh_url_to_repo"),
        "repo": str(repo),
    }


def planned_mr_payload(
    repo: Path,
    config: dict[str, str],
    *,
    source_branch: Optional[str],
    target_branch: Optional[str],
    title: Optional[str],
    description: Optional[str],
    remove_source_branch: bool,
    draft: bool,
) -> dict[str, Any]:
    actual_source = (source_branch or current_branch(repo)).strip()
    actual_target = (target_branch or default_target_branch(repo)).strip()
    actual_title = (title or f"ai-team: merge {actual_source}").strip()
    if draft and not actual_title.lower().startswith("draft:"):
        actual_title = f"Draft: {actual_title}"
    actual_description = (description or f"Automated ai-team delivery for branch `{actual_source}`.").strip()
    labels = [item for item in [(config.get("GITLAB_AUTODISPATCH_LABEL") or "").strip(), "ai-team:review"] if item]
    return {
        "status": "ok",
        "project_path": infer_project_path(repo, config),
        "gitlab_base_url": gitlab_base_url(config),
        "source_branch": actual_source,
        "target_branch": actual_target,
        "payload": {
            "source_branch": actual_source,
            "target_branch": actual_target,
            "title": actual_title,
            "description": actual_description,
            "remove_source_branch": "true" if remove_source_branch else "false",
            "labels": ",".join(labels),
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_merge_request(
    repo: Path,
    config: dict[str, str],
    *,
    source_branch: Optional[str],
    target_branch: Optional[str],
    title: Optional[str],
    description: Optional[str],
    remove_source_branch: bool,
    draft: bool,
) -> dict[str, Any]:
    planned = planned_mr_payload(
        repo,
        config,
        source_branch=source_branch,
        target_branch=target_branch,
        title=title,
        description=description,
        remove_source_branch=remove_source_branch,
        draft=draft,
    )
    token = (config.get("GITLAB_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("missing GITLAB_TOKEN")
    base_url = str(planned["gitlab_base_url"]).strip()
    project_path = str(planned["project_path"]).strip()
    if not base_url or not project_path:
        raise RuntimeError("missing gitlab base url or project path")
    encoded_project = project_api_path(project_path)
    source = str(planned["source_branch"])
    target = str(planned["target_branch"])
    existing = api_get(
        base_url,
        token,
        f"/api/v4/projects/{encoded_project}/merge_requests",
        {
            "state": "opened",
            "source_branch": source,
            "target_branch": target,
        },
    )
    if isinstance(existing, list) and existing:
        mr = existing[0]
        return {
            "status": "existing",
            "web_url": mr.get("web_url"),
            "iid": mr.get("iid"),
            "source_branch": source,
            "target_branch": target,
        }

    created = api_post(base_url, token, f"/api/v4/projects/{encoded_project}/merge_requests", planned["payload"])
    return {
        "status": "created",
        "web_url": created.get("web_url"),
        "iid": created.get("iid"),
        "source_branch": source,
        "target_branch": target,
    }


def find_open_merge_request(
    repo: Path,
    config: dict[str, str],
    *,
    source_branch: Optional[str],
    target_branch: Optional[str],
) -> dict[str, Any]:
    planned = planned_mr_payload(
        repo,
        config,
        source_branch=source_branch,
        target_branch=target_branch,
        title=None,
        description=None,
        remove_source_branch=False,
        draft=False,
    )
    token = (config.get("GITLAB_TOKEN") or "").strip()
    if not token:
        return {}
    base_url = str(planned["gitlab_base_url"]).strip()
    project_path = str(planned["project_path"]).strip()
    encoded_project = project_api_path(project_path)
    existing = api_get(
        base_url,
        token,
        f"/api/v4/projects/{encoded_project}/merge_requests",
        {
            "state": "opened",
            "source_branch": planned["source_branch"],
            "target_branch": planned["target_branch"],
        },
    )
    if isinstance(existing, list) and existing:
        return existing[0] if isinstance(existing[0], dict) else {}
    return {}


def merge_request_status(
    repo: Path,
    config: dict[str, str],
    *,
    source_branch: Optional[str],
    target_branch: Optional[str],
) -> dict[str, Any]:
    token = (config.get("GITLAB_TOKEN") or "").strip()
    planned = planned_mr_payload(
        repo,
        config,
        source_branch=source_branch,
        target_branch=target_branch,
        title=None,
        description=None,
        remove_source_branch=False,
        draft=False,
    )
    if not token:
        return {"status": "missing_token", "source_branch": planned["source_branch"], "target_branch": planned["target_branch"]}
    mr = find_open_merge_request(repo, config, source_branch=source_branch, target_branch=target_branch)
    if mr:
        pipeline_summary = latest_pipeline_for_ref(repo, config, ref=str(planned["source_branch"]))
        return {
            "status": "open",
            "iid": mr.get("iid"),
            "web_url": mr.get("web_url"),
            "title": mr.get("title"),
            "state": mr.get("state"),
            "pipeline": pipeline_summary,
        }
    return {"status": "missing", "source_branch": planned["source_branch"], "target_branch": planned["target_branch"]}


def latest_pipeline_for_ref(repo: Path, config: dict[str, str], *, ref: Optional[str], pipeline_id: Optional[int] = None) -> dict[str, Any]:
    token = (config.get("GITLAB_TOKEN") or "").strip()
    base_url = gitlab_base_url(config)
    project_path = infer_project_path(repo, config)
    if not token or not base_url or not project_path:
        return {"status": "missing_context"}
    encoded_project = project_api_path(project_path)
    selected_pipeline: dict[str, Any] = {}
    if pipeline_id:
        payload = api_get(base_url, token, f"/api/v4/projects/{encoded_project}/pipelines/{int(pipeline_id)}")
        selected_pipeline = payload if isinstance(payload, dict) else {}
    else:
        query: dict[str, Any] = {"per_page": 1, "order_by": "id", "sort": "desc"}
        if ref:
            query["ref"] = ref
        payload = api_get(base_url, token, f"/api/v4/projects/{encoded_project}/pipelines", query)
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            selected_pipeline = payload[0]
    if not selected_pipeline:
        return {"status": "missing"}
    pipeline_jobs = api_get(
        base_url,
        token,
        f"/api/v4/projects/{encoded_project}/pipelines/{int(selected_pipeline.get('id', 0))}/jobs",
        {"per_page": 100},
    )
    failed_jobs = [
        {
            "id": job.get("id"),
            "name": job.get("name"),
            "status": job.get("status"),
            "web_url": job.get("web_url"),
        }
        for job in (pipeline_jobs if isinstance(pipeline_jobs, list) else [])
        if isinstance(job, dict) and str(job.get("status") or "").strip().lower() == "failed"
    ]
    return {
        "status": "ok",
        "pipeline_id": selected_pipeline.get("id"),
        "pipeline_status": selected_pipeline.get("status"),
        "ref": selected_pipeline.get("ref"),
        "sha": selected_pipeline.get("sha"),
        "web_url": selected_pipeline.get("web_url"),
        "failed_jobs": failed_jobs,
    }


def resolve_note_body(*, body: Optional[str], body_file: Optional[str]) -> str:
    if body:
        return body
    if body_file:
        return Path(body_file).expanduser().read_text(encoding="utf-8")
    raise RuntimeError("missing note body")


def create_merge_request_note(
    repo: Path,
    config: dict[str, str],
    *,
    mr_iid: Optional[int],
    source_branch: Optional[str],
    target_branch: Optional[str],
    body: str,
) -> dict[str, Any]:
    token = (config.get("GITLAB_TOKEN") or "").strip()
    base_url = gitlab_base_url(config)
    project_path = infer_project_path(repo, config)
    if not token or not base_url or not project_path:
        raise RuntimeError("missing gitlab context")
    iid = int(mr_iid or 0)
    mr: dict[str, Any] = {}
    if iid <= 0:
        mr = find_open_merge_request(repo, config, source_branch=source_branch, target_branch=target_branch)
        iid = int(mr.get("iid") or 0)
    if iid <= 0:
        raise RuntimeError("missing merge request")
    encoded_project = project_api_path(project_path)
    note = api_post(
        base_url,
        token,
        f"/api/v4/projects/{encoded_project}/merge_requests/{iid}/notes",
        {"body": body},
    )
    return {
        "status": "created",
        "iid": iid,
        "note_id": note.get("id") if isinstance(note, dict) else None,
        "body_preview": body.splitlines()[:10],
    }


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    repo = resolve_repo(args.repo)
    doc_info = Path(args.doc_info).expanduser()
    secret_info = Path(args.secret_info).expanduser() if args.secret_info else default_secret_info()
    config = load_runtime_config(doc_info, secret_info)

    if args.command == "discover":
        payload = discover(repo, config)
    elif args.command == "create-project":
        payload = ensure_project(
            repo,
            config,
            project_name=args.project_name,
            project_path=args.project_path,
            namespace_id=args.namespace_id,
            visibility=args.visibility,
        )
        if args.write_report:
            write_json(Path(args.write_report).expanduser(), payload)
    elif args.command == "plan-mr":
        payload = planned_mr_payload(
            repo,
            config,
            source_branch=args.source_branch,
            target_branch=args.target_branch,
            title=args.title,
            description=args.description,
            remove_source_branch=bool(args.remove_source_branch),
            draft=bool(args.draft),
        )
        if args.write_report:
            write_json(Path(args.write_report).expanduser(), payload)
    elif args.command == "ensure-mr":
        payload = ensure_merge_request(
            repo,
            config,
            source_branch=args.source_branch,
            target_branch=args.target_branch,
            title=args.title,
            description=args.description,
            remove_source_branch=bool(args.remove_source_branch),
            draft=bool(args.draft),
        )
        if args.write_report:
            write_json(Path(args.write_report).expanduser(), payload)
    elif args.command == "mr-status":
        payload = merge_request_status(repo, config, source_branch=args.source_branch, target_branch=args.target_branch)
        if args.write_report:
            write_json(Path(args.write_report).expanduser(), payload)
    elif args.command == "pipeline-status":
        payload = latest_pipeline_for_ref(repo, config, ref=args.ref, pipeline_id=args.pipeline_id)
        if args.write_report:
            write_json(Path(args.write_report).expanduser(), payload)
    elif args.command == "mr-note":
        payload = create_merge_request_note(
            repo,
            config,
            mr_iid=args.mr_iid,
            source_branch=args.source_branch,
            target_branch=args.target_branch,
            body=resolve_note_body(body=args.body, body_file=args.body_file),
        )
        if args.write_report:
            write_json(Path(args.write_report).expanduser(), payload)
    else:
        raise RuntimeError(f"unsupported command: {args.command}")

    return emit(payload, bool(getattr(args, "json", False) or args.json))


if __name__ == "__main__":
    raise SystemExit(main())
