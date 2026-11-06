export default async function run(page, ui) {
  const out = {};
  const API = 'http://127.0.0.1:8901';

  // Signed-out home: public nav only
  await page.goto('http://127.0.0.1:3000/');
  await page.waitForTimeout(2000);
  out.signedOutNav = await page.evaluate(() => {
    const nav = document.querySelector('header nav');
    return nav ? nav.innerText.replace(/\n/g, ' | ') : 'NO NAV';
  });

  // Seed applicant with quote
  out.seed = await page.evaluate(async (api) => {
    const r = await fetch(api + '/qa/seed', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ business_name: 'Browser QA Co' }),
    });
    return r.json();
  }, API);

  // Customer sign-in via KYC page
  await page.goto('http://127.0.0.1:3000/kyc');
  await page.waitForTimeout(1500);
  await page.locator('#kyc-username').waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('#kyc-username').fill('qa_cust');
  await page.locator('#kyc-password').fill('CustomerQaPass123!');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForTimeout(2500);
  out.customerNavAfterLogin = await page.evaluate(() => {
    const nav = document.querySelector('header nav');
    return nav ? nav.innerText.replace(/\n/g, ' | ') : 'NO NAV';
  });
  out.customerBadge = await page.evaluate(() => document.body.innerText.match(/Signed in as[^\n]*/)?.[0] ?? 'none');

  // Point the applicant session at the seeded applicant
  await page.evaluate((id) => localStorage.setItem('udyamone.applicant-id', id), out.seed.applicant_id);

  // Orders page: place an order
  await page.goto('http://127.0.0.1:3000/orders');
  await page.waitForTimeout(2500);
  out.ordersPageHeading = await page.evaluate(() => document.querySelector('h1')?.innerText ?? 'NO H1');
  const snap1 = await ui.snapshot();
  out.confirmBoxPresent = snap1.includes('Confirm and place order');
  // tick the confirmation checkbox and place order
  const checkbox = page.locator('input[type=checkbox]').first();
  await checkbox.check();
  await page.waitForTimeout(300);
  await page.getByRole('button', { name: 'Confirm and place order' }).click();
  await page.waitForTimeout(3000);
  out.afterPlaceOrder = await page.evaluate(() => document.body.innerText.slice(0, 1200));
  out.viewMyOrdersBtn = await ui.snapshot().then((s) => s.includes('View My Orders'));

  // Duplicate submission: button should be disabled or produce an error
  const confirmBtn = page.getByRole('button', { name: 'Confirm and place order' });
  out.confirmBtnStillVisible = await confirmBtn.count() > 0;
  if (out.confirmBtnStillVisible) {
    try {
      await checkbox.check();
      await confirmBtn.click({ timeout: 3000 });
      await page.waitForTimeout(2000);
      out.duplicateAttempt = await page.evaluate(() =>
        document.body.innerText.match(/already exists[^\n]*|Order [^\n]*placed[^\n]*/)?.[0] ?? 'no-visible-message');
    } catch (e) { out.duplicateAttempt = 'button-disallowed'; }
  }

  // Open order details
  const detailBtn = page.getByRole('button', { name: /View details and timeline/ }).first();
  out.detailBtnCount = await detailBtn.count();
  if (out.detailBtnCount > 0) {
    await detailBtn.click();
    await page.waitForTimeout(2000);
    out.orderDetail = await page.evaluate(() => document.body.innerText.slice(0, 1500));
    out.timelineVisible = /Order timeline/.test(await page.evaluate(() => document.body.innerText));
  }

  // Header nav should show My Orders for customer
  out.myOrdersLink = await page.evaluate(() =>
    !!document.querySelector('header nav a[href="/orders"]'));
  return out;
}
