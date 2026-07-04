import os
import sys
import json
import webbrowser
import urllib.parse

_script_dir = os.path.dirname(os.path.abspath(__file__))
_agents_dir = os.path.dirname(_script_dir)
_root_dir = os.path.dirname(_agents_dir)
for _p in [os.path.join(_agents_dir, '.env'), os.path.join(_root_dir, '.env')]:
    if os.path.exists(_p):
        with open(_p) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#'):
                    _k, _, _v = _line.partition('=')
                    if _k and _v:
                        os.environ.setdefault(_k.strip(), _v.strip())


def save_env(filepath, updates):
    lines = []
    if os.path.exists(filepath):
        with open(filepath) as f:
            lines = f.readlines()

    updated_keys = set(updates.keys())
    existing_keys = set()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            key, _, _ = stripped.partition('=')
            key = key.strip()
            if key in updates:
                new_lines.append(f'{key}={updates[key]}\n')
                existing_keys.add(key)
                continue
        new_lines.append(line)

    for key, val in updates.items():
        if key not in existing_keys:
            new_lines.append(f'{key}={val}\n')

    with open(filepath, 'w') as f:
        f.writelines(new_lines)


def main():
    client_key = os.environ.get('TIKTOK_CLIENT_KEY', '')
    client_secret = os.environ.get('TIKTOK_CLIENT_SECRET', '')
    if not client_key or not client_secret:
        print('ERROR: TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET must be set in .env')
        sys.exit(1)

    ngrok_url = ''
    redirect_url = ''
    for arg in sys.argv[1:]:
        if 'code=' in arg:
            redirect_url = arg.strip()
        elif arg.startswith('http'):
            ngrok_url = arg.strip().rstrip('/')

    if not redirect_url:
        print()
        redirect_url = input('Redirected URL: ').strip()

    if not ngrok_url:
        ngrok_url = input('Enter ngrok URL (e.g. https://xxxx.ngrok-free.dev): ').strip().rstrip('/')
    if not ngrok_url and redirect_url:
        parsed = urllib.parse.urlparse(redirect_url)
        ngrok_url = f'{parsed.scheme}://{parsed.netloc}'
    if not ngrok_url:
        print('ngrok URL required.')
        sys.exit(1)

    redirect_uri = f'{ngrok_url}/callback'

    auth_url = (
        'https://www.tiktok.com/v2/auth/authorize/'
        f'?client_key={client_key}'
        '&scope=user.info.basic,video.upload'
        '&response_type=code'
        f'&redirect_uri={redirect_uri}'
        '&state=timi_sandbox'
    )

    if not redirect_url:
        print('=' * 60)
        print('TikTok OAuth Setup')
        print('=' * 60)
        print()
        print('Step 1: Open this URL in your browser:')
        print()
        print(auth_url)
        print()
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

        print('Step 2: Authorize the app in your browser.')
        print()
        print('Step 3: After authorizing, your browser will redirect to a URL that shows')
        print('        an error page (ngrok server not needed). That is OK.')
        print()
        print('Copy the FULL redirect URL from your browser address bar and paste it:')
        print()
        redirect_url = input('Redirected URL: ').strip()

    if not redirect_url or 'code=' not in redirect_url:
        print('No authorization code found in the URL.')
        sys.exit(1)

    code = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)['code'][0]

    print()
    print('Step 4: Exchanging code for tokens...')
    print()

    import requests
    resp = requests.post(
        'https://open.tiktokapis.com/v2/oauth/token/',
        data={
            'client_key': client_key,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        print(f'Token exchange failed: {resp.status_code}')
        print(resp.text)
        sys.exit(1)

    data = resp.json()
    access_token = data.get('access_token', '')
    open_id = data.get('open_id', '')
    refresh_token = data.get('refresh_token', '')

    if not access_token or not open_id:
        print('Missing access_token or open_id in response.')
        print(json.dumps(data, indent=2))
        sys.exit(1)

    print(f'SUCCESS! Tokens received.')
    print(f'  Open ID: {open_id}')
    print()

    updates = {
        'TIKTOK_ACCESS_TOKEN': access_token,
        'TIKTOK_OPEN_ID': open_id,
    }
    if refresh_token:
        updates['TIKTOK_REFRESH_TOKEN'] = refresh_token

    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(scripts_dir)
    root_dir = os.path.dirname(agents_dir)

    dotenv_path = os.path.join(root_dir, '.env')
    agents_env_path = os.path.join(agents_dir, '.env')

    for env_path in [dotenv_path, agents_env_path]:
        if os.path.exists(env_path):
            save_env(env_path, updates)
            print(f'Updated: {env_path}')

    print()
    print('TikTok OAuth setup complete! You can now test uploads.')
    print('ngrok is no longer needed after this — tokens saved to .env files.')


if __name__ == '__main__':
    main()
