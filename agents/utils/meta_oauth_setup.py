"""
Meta (Facebook + Instagram) OAuth Setup Script

Run: python -m agents.utils.meta_oauth_setup [existing_token]
Or:  python utils/meta_oauth_setup.py          (from agents/)

Guides through Facebook OAuth, exchanges for long-lived Page token,
discovers Page ID and Instagram Account ID, and persists to .env files.
"""
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


def _graph_get(path, token, params=None):
    import requests
    p = {'access_token': token}
    if params:
        p.update(params)
    resp = requests.get(f'https://graph.facebook.com/v25.0{path}', params=p, timeout=15)
    if resp.status_code != 200:
        print(f'  ERROR {resp.status_code}: {resp.json().get("error", {}).get("message", resp.text)[:200]}')
        return None
    return resp.json()


def validate_token(token):
    data = _graph_get('/me', token, {'fields': 'id,name'})
    if data:
        print(f'  Token valid — User: {data.get("name")} (ID: {data.get("id")})')
        return data
    return None


def exchange_token(token, app_id, app_secret):
    import requests
    resp = requests.get(
        'https://graph.facebook.com/v25.0/oauth/access_token',
        params={
            'grant_type': 'fb_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'fb_exchange_token': token,
        },
        timeout=15,
    )
    if resp.status_code == 200:
        new_token = resp.json().get('access_token')
        if new_token:
            print('  Token exchanged for long-lived token.')
            return new_token
    print(f'  Token exchange failed: {resp.status_code} {resp.text[:200]}')
    return None


def discover_pages(token):
    data = _graph_get('/me/accounts', token, {'fields': 'id,name,access_token,instagram_business_account'})
    if not data:
        return []
    pages = data.get('data', [])
    if not pages:
        print('  No Facebook Pages found for this user.')
        print('  Make sure you have a Facebook Page and have added the Pages API product.')
        return []
    print(f'  Found {len(pages)} page(s):')
    for i, page in enumerate(pages):
        ig = page.get('instagram_business_account', {})
        ig_id = ig.get('id', 'N/A') if ig else 'N/A'
        print(f'    [{i}] {page.get("name")} (ID: {page.get("id")})')
        print(f'        Instagram Account ID: {ig_id}')
        print(f'        Has page token: {"Yes" if page.get("access_token") else "No"}')
    return pages


def main():
    import requests

    print('=' * 60)
    print('Meta (Facebook & Instagram) OAuth Setup')
    print('=' * 60)
    print()

    app_id = os.environ.get('FACEBOOK_APP_ID', '')
    app_secret = os.environ.get('FACEBOOK_APP_SECRET', '')
    if not app_id or not app_secret:
        print('ERROR: FACEBOOK_APP_ID and FACEBOOK_APP_SECRET must be set in .env')
        print('Create your Facebook App at https://developers.facebook.com/apps/')
        print('Add "Instagram Graph API" and "Pages API" products to the app.')
        sys.exit(1)

    existing_token = sys.argv[1] if len(sys.argv) > 1 else ''
    if not existing_token:
        existing_token = os.environ.get('FACEBOOK_ACCESS_TOKEN', '')

    token = ''
    if existing_token:
        print('Validating existing token...')
        info = validate_token(existing_token)
        if info:
            token = existing_token
        else:
            print('Existing token is invalid. Need a new one.')
            token = ''

    if not token:
        print()
        print('Step 1: Get a short-lived access token')
        print()
        print('  Option A — Use Graph API Explorer (easiest):')
        print(f'    1. Go to: https://developers.facebook.com/tools/explorer/{app_id}/')
        print('    2. Select your app and Page')
        print(f'    3. Add permissions: pages_show_list, pages_read_engagement,')
        print('       pages_manage_posts, instagram_basic, instagram_content_publish')
        print('    4. Click "Generate Access Token"')
        print('    5. Copy the token and paste it below')
        print()
        print('  Option B — Use the OAuth URL below:')
        redirect_uri = 'https://developers.facebook.com/tools/explorer/callback/'
        oauth_url = (
            'https://www.facebook.com/v25.0/dialog/oauth'
            f'?client_id={app_id}'
            '&redirect_uri=' + urllib.parse.quote(redirect_uri, safe='') +
            '&scope=pages_show_list,pages_read_engagement,pages_manage_posts,'
            'instagram_basic,instagram_content_publish,pages_manage_metadata'
            '&response_type=token'
        )
        print(f'  {oauth_url}')
        print()
        try:
            webbrowser.open(oauth_url)
        except Exception:
            pass

        token = input('Enter access token (from Graph API Explorer or OAuth URL): ').strip()
        if not token:
            print('No token provided.')
            sys.exit(1)

        info = validate_token(token)
        if not info:
            print('Token validation failed. Make sure the token has the correct permissions.')
            sys.exit(1)

    print()
    print('Step 2: Exchange for long-lived Page token...')
    print()

    long_token = exchange_token(token, app_id, app_secret)
    if not long_token:
        print('Could not exchange token. The short-lived token may already be a long-lived token.')
        print('Proceeding with existing token...')
        long_token = token

    print()
    print('Step 3: Discovering Pages and Instagram Account...')
    print()

    pages = discover_pages(long_token)
    if not pages:
        sys.exit(1)

    selected_page = None
    if len(pages) == 1:
        selected_page = pages[0]
        print(f'\nAuto-selected page: {selected_page.get("name")}')
    else:
        idx = int(input(f'\nSelect page number (0-{len(pages)-1}): ').strip())
        selected_page = pages[idx]

    page_id = selected_page['id']
    page_name = selected_page.get('name', '')
    page_token = selected_page.get('access_token', long_token)

    ig_business = selected_page.get('instagram_business_account')
    ig_account_id = ig_business.get('id', '') if ig_business else ''

    if not ig_account_id:
        print()
        print('  Instagram Account ID not linked to this Page.')
        print('  Make sure:')
        print('    1. Your Instagram account is a Business account')
        print('    2. It is linked to the Facebook Page in Meta Business Suite')
        print('    3. The "Instagram Graph API" product is added to your app')
        print()
        manual = input('  Enter Instagram Account ID manually (or press Enter to skip): ').strip()
        if manual:
            ig_account_id = manual

    print()
    print('Step 4: Saving to .env files...')
    print()

    updates = {
        'FACEBOOK_ACCESS_TOKEN': page_token,
        'FACEBOOK_PAGE_ID': page_id,
    }
    if ig_account_id:
        updates['INSTAGRAM_ACCOUNT_ID'] = ig_account_id

    for env_path in [os.path.join(_root_dir, '.env'), os.path.join(_agents_dir, '.env')]:
        if os.path.exists(env_path):
            save_env(env_path, updates)
            print(f'  Updated: {env_path}')

    print()
    print('=' * 60)
    print('Setup Complete!')
    print('=' * 60)
    print(f'  Page:        {page_name} ({page_id})')
    if ig_account_id:
        print(f'  Instagram:   {ig_account_id}')
    print()
    print('  The token has been persisted to both .env files.')
    print('  Next steps:')
    print('    1. Verify with: python agents/scripts/health.py')
    print('    2. Run pipeline with Facebook/Instagram publishing')
    print()


if __name__ == '__main__':
    main()
