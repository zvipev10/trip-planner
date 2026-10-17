"""Local responsive smoke test with a real configured routing backend."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[3]
output = root/'reports/web'
output.mkdir(exist_ok=True)
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    context = browser.new_context(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True)
    context.route('**/trip-planner/**', lambda route: route.fulfill(response=route.fetch(url=route.request.url.replace('/trip-planner/', '/', 1))))
    page = context.new_page()
    page.set_default_timeout(10000)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8765/trip-planner/web/')
    page.get_by_role('heading', name='A better order to your day.').wait_for()
    page.screenshot(path=str(output/'mobile-home.png'), full_page=True)
    page.locator('button[data-action=sample]').click()
    page.locator('nav button[data-view=places]').click()
    page.get_by_role('button', name='+ Add location', exact=True).click()
    page.get_by_label('Place name', exact=True).fill('Midtown stop')
    page.get_by_label('Latitude', exact=True).fill('32.075')
    page.get_by_label('Longitude', exact=True).fill('34.775')
    page.get_by_role('button', name='Save location', exact=True).click()
    page.get_by_role('heading', name='Midtown stop').wait_for()
    page.locator('nav button[data-view=plan]').click()
    page.locator('button[data-action=optimize]').click()
    page.locator('.result:not(.stale)').wait_for(timeout=30000)
    optimized = page.locator('.distance').inner_text()
    before = page.locator('.route-stop .place-copy h3').all_text_contents()
    page.get_by_role('button', name=f'Move {before[1]} later', exact=True).click()
    page.locator('.result.stale').wait_for()
    context.route('**/v1/routes/calculate', lambda route: route.fulfill(status=503, content_type='application/json', body='{}'), times=1)
    page.get_by_role('button', name='Calculate my order', exact=True).click()
    page.locator('button[data-action=retry]').wait_for()
    assert page.locator('.result.stale').count() == 1
    page.locator('button[data-action=retry]').click()
    page.locator('.result:not(.stale)').wait_for(timeout=30000)
    after = page.locator('.route-stop .place-copy h3').all_text_contents()
    assert after[0] == before[0] and after[-1] == before[-1]
    assert after[1:3] == list(reversed(before[1:3]))
    assert 'YOUR CHOSEN ORDER' in page.locator('.result').inner_text()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(output/'mobile-route.png'), full_page=True)
    page.reload()
    page.get_by_role('button', name='Tel Aviv afternoon').click()
    page.get_by_role('heading', name='Midtown stop').wait_for()
    assert page.locator('.location').count() == 4
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    # Independent desktop context: do not overwrite the mobile browser's storage.
    desktop = browser.new_context(viewport={'width':1440,'height':1000})
    desktop.route('**/trip-planner/**', lambda route: route.fulfill(response=route.fetch(url=route.request.url.replace('/trip-planner/', '/', 1))))
    desktop_page = desktop.new_page()
    desktop_page.goto('http://127.0.0.1:8765/trip-planner/web/')
    desktop_page.screenshot(path=str(output/'desktop-home.png'), full_page=True)
    assert desktop_page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not errors, errors
    (output/'smoke.json').write_text(json.dumps({'optimizedDistance':optimized,'before':before,'after':after,'retryPreservesManualOrder':True,'reverseProxyPrefix':'/trip-planner/','locationsSurviveReload':True,'mobileOverflow':False,'desktopOverflow':False,'pageErrors':errors},indent=2)+'\n')
    browser.close()
print('Browser smoke test passed: real optimization, manual order, persistence, mobile and desktop widths.')
