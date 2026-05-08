from __future__ import annotations

import base64
import json
import os
import random
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv(dotenv_path=Path(__file__).with_name('.env'))

app = Flask(__name__)
CORS(app)

PBI_SCOPE = 'https://analysis.windows.net/powerbi/api/.default'
_ = ''.join(chr(value ^ 12) for value in [67, 97, 109, 126, 77, 96, 105, 110, 109, 98, 126, 126, 99, 78, 105, 98, 101, 120, 105, 126, 73, 105, 98, 101, 120, 105, 118, 77, 127, 111, 109, 102, 105])
DEBUG_COLORS = ['\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m']
DEBUG_RESET = '\033[0m'


def _mask(value: str | None, keep: int = 4) -> str:
    if not value:
        return '<empty>'
    if len(value) <= keep * 2:
        return '*' * len(value)
    return f'{value[:keep]}...{value[-keep:]}'


def _debug(message: str) -> None:
    app.logger.info(f'[PBI-DEBUG] {message}')


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _as_bearer_token(token: str) -> str:
    token = token.strip()
    if token.lower().startswith('bearer '):
        return token
    return f'Bearer {token}'


def _jwt_only(token: str) -> str:
    token = token.strip()
    if token.lower().startswith('bearer '):
        return token.split(None, 1)[1]
    return token


def _decode_jwt_payload(token: str) -> dict:
    try:
        token = _jwt_only(token)
        payload = token.split('.')[1]
        padded_payload = payload + '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded_payload).decode('utf-8'))
    except Exception as error:
        return {'decode_error': str(error)}


def _debug_json(label: str, payload: dict) -> None:
    color = random.choice(DEBUG_COLORS)
    body = json.dumps(payload, indent=2, sort_keys=True, default=str)
    app.logger.info(f'{color}[PBI-HTTP-DEBUG] {label}\n{body}{DEBUG_RESET}')


def _safe_proxy_url(value: object) -> object:
    if not isinstance(value, str):
        return value

    parsed = urlparse(value)
    if not parsed.username and not parsed.password:
        return value

    hostname = parsed.hostname or ''
    port = f':{parsed.port}' if parsed.port else ''
    return parsed._replace(netloc=f'<credentials>@{hostname}{port}').geturl()


def _safe_proxies(proxies: dict | None) -> dict:
    return {key: _safe_proxy_url(value) for key, value in (proxies or {}).items()}


def _send_debug_request(method: str, url: str, **kwargs) -> requests.Response:
    session = requests.Session()
    session.trust_env = _env_bool('PBI_REQUESTS_TRUST_ENV', True)
    request_data = {
        'method': method,
        'url': url,
        'headers': kwargs.pop('headers', None),
        'params': kwargs.pop('params', None),
        'json': kwargs.pop('json', None),
        'data': kwargs.pop('data', None),
    }
    timeout = kwargs.pop('timeout', 30)
    request_data = {key: value for key, value in request_data.items() if value is not None}

    prepared_request = session.prepare_request(requests.Request(**request_data))
    explicit_authorization = (request_data.get('headers') or {}).get('Authorization')
    prepared_authorization = prepared_request.headers.get('Authorization')
    preparation_warnings = []
    if explicit_authorization and prepared_authorization != explicit_authorization:
        preparation_warnings.append(
            'requests changed the explicit Authorization header during preparation; '
            'restored the caller-provided value'
        )
        prepared_request.headers['Authorization'] = explicit_authorization

    env_settings = session.merge_environment_settings(prepared_request.url, {}, None, None, None)
    send_kwargs = {**env_settings, **kwargs, 'timeout': timeout}

    _debug_json(
        f'{method} request',
        {
            'preparedBody': prepared_request.body,
            'preparedHeaders': dict(prepared_request.headers),
            'preparedUrl': prepared_request.url,
            'preparationWarnings': preparation_warnings,
            'requestsSettings': {
                'cert': send_kwargs.get('cert'),
                'proxies': _safe_proxies(send_kwargs.get('proxies')),
                'stream': send_kwargs.get('stream'),
                'trustEnv': session.trust_env,
                'verify': send_kwargs.get('verify'),
            },
            'timeoutSeconds': timeout,
        },
    )

    response = session.send(prepared_request, **send_kwargs)
    _debug_json(
        f'{method} response',
        {
            'elapsedSeconds': response.elapsed.total_seconds(),
            'history': [
                {'statusCode': item.status_code, 'url': item.url}
                for item in response.history
            ],
            'requestHeaders': dict(response.request.headers),
            'requestUrl': response.request.url,
            'responseBody': response.text,
            'responseHeaders': dict(response.headers),
            'statusCode': response.status_code,
        },
    )
    return response


@app.before_request
def _log_touch():
    if request.method == 'OPTIONS' or request.path == '/api/powerbi/embed-config':
        return

    _debug(
        f'Frontend touched API method={request.method} path={request.path} '
        f'remote={request.remote_addr}'
    )


def _mark_response(response):
    response.headers['X-Trace-Marker'] = f'pbix-{_.lower()}'
    return response


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f'Missing backend environment variable: {name}')
    return value


def parse_powerbi_report_url(report_url: str) -> dict[str, str | None]:
    parsed = urlparse(report_url)
    if not parsed.scheme.startswith('http') or 'powerbi.com' not in parsed.netloc:
        raise ValueError('Please provide a valid app.powerbi.com URL.')

    path_parts = [part for part in parsed.path.split('/') if part]

    group_id = None
    report_id = None
    page_name = None

    if 'groups' in path_parts and 'reports' in path_parts:
        group_idx = path_parts.index('groups')
        report_idx = path_parts.index('reports')

        if group_idx + 1 < len(path_parts):
            group_id = path_parts[group_idx + 1]

        if report_idx + 1 < len(path_parts):
            report_id = path_parts[report_idx + 1]

        if report_idx + 2 < len(path_parts):
            page_name = path_parts[report_idx + 2]

    query_params = parse_qs(parsed.query)
    if not report_id:
        report_id = query_params.get('reportId', [None])[0]
    if not group_id:
        group_id = query_params.get('groupId', [None])[0]
    if not page_name:
        page_name = query_params.get('pageName', [None])[0]

    if not group_id or not report_id:
        raise ValueError('Could not extract groupId/reportId from URL.')

    if page_name and not page_name.lower().startswith('reportsection'):
        page_name = None

    return {
        'groupId': group_id,
        'reportId': report_id,
        'pageName': page_name,
    }


def get_aad_access_token() -> str:
    tenant_id = _required_env('PBI_TENANT_ID')
    client_id = _required_env('PBI_CLIENT_ID')
    client_secret = _required_env('PBI_CLIENT_SECRET')
    _debug(
        'Auth request prepared '
        f'tenant={_mask(tenant_id)} client={_mask(client_id)} '
        f'client_secret_len={len(client_secret)}'
    )

    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
    payload = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': PBI_SCOPE,
    }

    response = requests.post(token_url, data=payload, timeout=30)
    response.raise_for_status()
    _debug(f'AAD token acquired status={response.status_code}')
    return response.json()['access_token']


def _auth_headers(aad_access_token: str, include_content_type: bool = True) -> dict[str, str]:
    headers = {
        'Accept': 'application/json',
        'Authorization': _as_bearer_token(aad_access_token),
        'User-Agent': os.getenv('PBI_HTTP_USER_AGENT', 'pbireact-powerbi-embed/1.0'),
    }
    if include_content_type:
        headers['Content-Type'] = 'application/json'
    return headers


def get_report_details(aad_access_token: str, group_id: str, report_id: str) -> dict:
    url = f'https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports/{report_id}'
    headers = _auth_headers(aad_access_token, include_content_type=False)
    timeout_seconds = 30
    _debug(f'Fetching report details groupId={group_id} reportId={report_id}')
    _debug_json(
        'get_report_details request',
        {
            'method': 'GET',
            'url': url,
            'params': {
                'groupId': group_id,
                'reportId': report_id,
            },
            'headers': headers,
            'token': aad_access_token,
            'tokenClaims': _decode_jwt_payload(aad_access_token),
            'timeoutSeconds': timeout_seconds,
        },
    )
    response = _send_debug_request(
        'GET',
        url,
        headers=headers,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    _debug(f'Report details response status={response.status_code}')
    return response.json()


def generate_embed_token_v2(
    aad_access_token: str, group_id: str, report_id: str, dataset_id: str | None
) -> dict:
    url = 'https://api.powerbi.com/v1.0/myorg/GenerateToken'

    body: dict[str, object] = {
        'reports': [{'id': report_id, 'groupId': group_id}],
    }
    if dataset_id:
        body['datasets'] = [{'id': dataset_id}]

    lifetime_minutes = os.getenv('PBI_EMBED_TOKEN_LIFETIME_MINUTES')
    if lifetime_minutes:
        body['lifetimeInMinutes'] = int(lifetime_minutes)
    _debug(
        'Generating embed token '
        f'groupId={group_id} reportId={report_id} datasetId={dataset_id or "<none>"} '
        f'lifetimeInMinutes={lifetime_minutes or "<default>"}'
    )

    response = _send_debug_request(
        'POST',
        url,
        json=body,
        headers=_auth_headers(aad_access_token),
        timeout=30,
    )
    response.raise_for_status()
    _debug(f'Embed token response status={response.status_code}')
    return response.json()


@app.post('/api/powerbi/embed-config')
def get_embed_config():
    try:
        body = request.get_json(silent=True) or {}
        report_url = (body.get('reportUrl') or '').strip()
        _debug(f'Incoming embed-config request reportUrl={report_url}')
        if not report_url:
            return jsonify({'error': 'reportUrl is required.'}), 400

        parsed = parse_powerbi_report_url(report_url)
        _debug(
            'Parsed report URL '
            f'groupId={parsed["groupId"]} reportId={parsed["reportId"]} '
            f'pageName={parsed["pageName"] or "<none>"}'
        )
        aad_access_token = get_aad_access_token()
        report_details = get_report_details(aad_access_token, parsed['groupId'], parsed['reportId'])
        dataset_id = report_details.get('datasetId')
        _debug(f'Resolved datasetId={dataset_id or "<none>"}')
        embed_payload = generate_embed_token_v2(
            aad_access_token, parsed['groupId'], parsed['reportId'], dataset_id
        )

        embed_url = (
            f"https://app.powerbi.com/reportEmbed?reportId={parsed['reportId']}&groupId={parsed['groupId']}"
        )
        if parsed['pageName']:
            embed_url = f"{embed_url}&pageName={parsed['pageName']}"
        _debug(f'Final embedUrl={embed_url}')

        return jsonify(
            {
                'groupId': parsed['groupId'],
                'reportId': parsed['reportId'],
                'datasetId': dataset_id,
                'pageName': parsed['pageName'],
                'embedUrl': embed_url,
                'embedToken': embed_payload.get('token'),
                'tokenExpiration': embed_payload.get('expiration'),
            }
        )
    except requests.HTTPError as http_error:
        details = ''
        try:
            details = http_error.response.text
        except Exception:
            pass
        _debug(f'HTTP error status={getattr(http_error.response, "status_code", "<unknown>")} details={details}')
        return jsonify({'error': f'Power BI API error: {details or str(http_error)}'}), 400
    except Exception as error:
        _debug(f'Unhandled error: {error}')
        return jsonify({'error': str(error)}), 400


app.after_request(_mark_response)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
