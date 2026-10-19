"""Optional browser check against a running local website (Playwright is test-only).

python -m pip install playwright
python -m playwright install chromium
python scripts/browser_smoke.py --url http://127.0.0.1:8000
Add --run-replay to exercise the full background pipeline with the supplied pack.
Use a separate website --data-dir for these generated test accounts.
"""
import argparse
import json
import secrets
import uuid
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--browser-path')
    parser.add_argument('--run-replay', action='store_true')
    args = parser.parse_args()
    key = uuid.uuid4().hex[:12]
    email, password = f'browser-{key}@example.test', secrets.token_urlsafe(24)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **({'executable_path':args.browser_path} if args.browser_path else {}))
        page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.url+'/#/signup')
        page.get_by_label('Full name',exact=True).fill('Browser Reviewer')
        page.get_by_label('Email address',exact=True).fill(email)
        page.get_by_label('Password',exact=True).fill(password)
        page.get_by_role('button',name='Create account',exact=True).click()
        page.get_by_role('heading',name='Overview',exact=True).wait_for()
        page.reload()
        page.get_by_role('heading',name='Overview',exact=True).wait_for()
        page.get_by_role('link',name='Viewers',exact=True).click()
        page.get_by_placeholder('Search by viewer ID…').fill('U-02825')
        page.wait_for_timeout(700)
        page.get_by_role('link',name='U-02825',exact=True).click()
        page.get_by_role('heading',name='U-02825',exact=True).wait_for()
        page.get_by_role('link',name='Experiments',exact=True).click()
        page.get_by_role('heading',name='No identified population uplift',exact=True).wait_for()
        page.get_by_role('link',name='Reports',exact=True).click()
        page.get_by_role('button',name='Read report').first.click()
        page.locator('#report-preview:not([hidden])').wait_for()
        with page.expect_download() as download:
            page.get_by_role('link',name='Download Final report',exact=True).click()
        assert download.value.suggested_filename=='final_report.md'
        if args.run_replay:
            page.get_by_role('link',name='Replay studio',exact=True).click()
            page.get_by_label('Simulator seed',exact=True).fill('browser-'+key)
            page.get_by_role('button',name='Start replay',exact=True).click()
            page.locator('[data-action="open-run"]').first.wait_for(state='visible',timeout=180000)
            page.locator('[data-action="open-run"]').first.click()
            page.get_by_role('heading',name='Overview',exact=True).wait_for()
            assert page.locator('#run-select').input_value()!='sample'
        page.goto(args.url+'/#/account')
        page.get_by_label('Full name',exact=True).fill('Reviewed Account')
        new_password = secrets.token_urlsafe(24)
        page.get_by_label('Current password',exact=True).fill(password)
        page.get_by_label('New password',exact=True).fill(new_password)
        page.get_by_label('Confirm new password',exact=True).fill(new_password)
        page.get_by_role('button',name='Save changes',exact=True).click()
        page.get_by_role('heading',name='Reviewed Account',exact=True).wait_for()
        page.get_by_role('button',name='Sign out of this browser',exact=True).click()
        page.get_by_role('heading',name='Welcome back.',exact=True).wait_for()
        page.get_by_label('Email address',exact=True).fill(email)
        page.get_by_label('Password',exact=True).fill(new_password)
        page.get_by_role('button',name='Sign in',exact=True).click()
        page.get_by_role('heading',name='Overview',exact=True).wait_for()
        page.set_viewport_size({'width':390,'height':844})
        page.wait_for_timeout(250)
        assert page.locator('#sidebar').evaluate("el => getComputedStyle(el).visibility")=='hidden'
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.get_by_role('button',name='Toggle navigation',exact=True).click()
        page.get_by_role('link',name='Viewers',exact=True).click()
        page.get_by_role('heading',name='Viewers',exact=True).wait_for()
        assert not errors,errors
        print(json.dumps({'passed':True,'browser':'Chromium','mobile_width':390,
                          'full_replay':args.run_replay,'javascript_errors':errors}))
        browser.close()


if __name__=='__main__':
    main()
