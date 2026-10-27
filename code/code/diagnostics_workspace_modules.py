import json
import os
import time
from auth import get_token
from config import BASE_URL, RAW_JSON_DIR
from api import get_workspaces
import requests

OUT_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(OUT_DIR, exist_ok=True)

def load_workspaces(token):
    payload = get_workspaces(token)
    if isinstance(payload, dict) and 'data' in payload:
        return payload['data']
    if isinstance(payload, list):
        return payload
    return []


def diagnose():
    token = get_token()
    ws_list = load_workspaces(token)
    results = []
    headers = {'Authorization': f'Bearer {token}'}
    for ws in ws_list:
        wid = ws.get('workspaceId') or ws.get('id') or ws.get('workspace_id')
        name = ws.get('workspaceName') or ws.get('name') or ws.get('workspace_name')
        if wid is None:
            continue
        url = f"{BASE_URL}/workspace/{wid}/modules"
        try:
            r = requests.get(url, headers=headers, timeout=30)
            status = r.status_code
            text = r.text[:2000]
            is_json = False
            data_len = None
            try:
                j = r.json()
                is_json = True
                if isinstance(j, dict) and 'data' in j and isinstance(j['data'], list):
                    data_len = len(j['data'])
            except Exception:
                j = None
            results.append({'workspace_id': wid, 'workspace_name': name, 'url': url, 'status': status, 'text_snippet': text[:500], 'is_json': is_json, 'data_len': data_len})
        except Exception as e:
            results.append({'workspace_id': wid, 'workspace_name': name, 'url': url, 'status': 'error', 'error': str(e)})
        time.sleep(0.05)

    out_path = os.path.join(OUT_DIR, 'diagnostics_workspace_modules.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    # summary
    non_empty = [r for r in results if r.get('data_len') and r.get('data_len') > 0]
    print(f'Total workspaces checked: {len(results)}')
    print(f'Workspaces with modules: {len(non_empty)}')
    if non_empty:
        print('Examples:')
        print(json.dumps(non_empty[:5], indent=2))
    print('Detailed log written to', out_path)

if __name__ == '__main__':
    diagnose()
