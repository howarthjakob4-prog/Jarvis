#!/usr/bin/env python3
"""Deploy the Jarvis phone-link bridge worker + its KV namespace.

Usage:
    deploy.py

Creates (or reuses) the KV namespace "jarvis-link", uploads bridge/worker.js
as the "jarvis-link-bridge" worker with the KV binding, and prints the live URL.
Auth uses the stored custom.cloudflare credential via authd surrogates.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    read_json_response,
)

API = "https://api.cloudflare.com/client/v4"
ALLOWED = ["api.cloudflare.com"]
CRED = "custom.cloudflare"
SCRIPT_NAME = "jarvis-link-bridge"
KV_TITLE = "jarvis-link"
HERE = os.path.dirname(os.path.abspath(__file__))


def api_request(method, url, body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    add_surrogate_to_request(req, CRED, allowed_hosts=ALLOWED)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800]
        raise SystemExit(f"API {method} {url} -> {e.code}: {detail}")
    data = read_json_response(resp)
    if not data.get("success", True):
        raise SystemExit(f"API error: {json.dumps(data.get('errors'))[:500]}")
    return data["result"]


def get_account_id():
    accounts = api_request("GET", f"{API}/accounts")
    if not accounts:
        raise SystemExit("no Cloudflare accounts found on this token")
    acct = accounts[0]
    print(f"account: {acct['name']} ({acct['id']})")
    return acct["id"]


def get_or_create_kv(account_id):
    nss = api_request("GET", f"{API}/accounts/{account_id}/storage/kv/namespaces")
    for ns in nss:
        if ns.get("title") == KV_TITLE:
            print(f"KV namespace '{KV_TITLE}' exists ({ns['id']})")
            return ns["id"]
    ns = api_request(
        "POST",
        f"{API}/accounts/{account_id}/storage/kv/namespaces",
        body=json.dumps({"title": KV_TITLE}).encode(),
        headers={"Content-Type": "application/json"},
    )
    print(f"KV namespace '{KV_TITLE}' created ({ns['id']})")
    return ns["id"]


def upload_worker(account_id, ns_id):
    script = open(os.path.join(HERE, "worker.js"), "rb").read()
    boundary = "----jarvislinkboundary"
    metadata = json.dumps({
        "main_module": "worker.js",
        "bindings": [
            {"type": "kv_namespace", "name": "LINK_KV", "namespace_id": ns_id}
        ],
    }).encode()
    body = (
        b"--" + boundary.encode() + b"\r\n"
        b'Content-Disposition: form-data; name="metadata"\r\n'
        b"Content-Type: application/json\r\n\r\n"
        + metadata +
        b"\r\n--" + boundary.encode() + b"\r\n"
        b'Content-Disposition: form-data; name="worker.js"; filename="worker.js"\r\n'
        b"Content-Type: application/javascript+module\r\n\r\n"
        + script +
        b"\r\n--" + boundary.encode() + b"--\r\n"
    )
    result = api_request(
        "PUT",
        f"{API}/accounts/{account_id}/workers/scripts/{SCRIPT_NAME}",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    print(f"script '{SCRIPT_NAME}' uploaded (id={result.get('id')})")


def main():
    account_id = get_account_id()
    ns_id = get_or_create_kv(account_id)
    upload_worker(account_id, ns_id)
    sub = api_request("GET", f"{API}/accounts/{account_id}/workers/subdomain")
    url = f"https://{SCRIPT_NAME}.{sub['subdomain']}.workers.dev"
    print(f"LIVE: {url}")


if __name__ == "__main__":
    main()
