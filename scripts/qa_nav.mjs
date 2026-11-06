export default async function run(page, ui) {
  const out = {};
  // Signed-out home: public nav only
  await page.goto('http://127.0.0.1:3000/');
  await page.waitForTimeout(2500);
  const navText = await page.evaluate(() => {
    const nav = document.querySelector('header nav');
    return nav ? nav.innerText : 'NO NAV';
  });
  out.signedOutNav = navText;

  // ---- Customer journey ----
  await page.goto('http://127.0.0.1:3000/kyc');
  await page.waitForTimeout(2000);
  const preLoginSnapshot = await ui.snapshot();
  out.kycHasSignIn = preLoginSnapshot.includes('Sign in');

  // Seed applicant via QA backend and get its ID
  const seedRes = await page.evaluate(async () => {
    const r = await fetch('http://127.0.0.1:8901/qa/seed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ business_name: 'Browser QA Co' }),
    });
    return r.json();
  });
  out.seed = seedRes;

  // Sign in as customer
  await page.locator('#kyc-username').fill('qa_cust');
  await page.locator('#kyc-password').fill('CustomerQaPass123!');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForTimeout(2000);
  out.customerNavAfterLogin = await page.evaluate(() => {
    const nav = document.querySelector('header nav');
    return nav ? nav.innerText : 'NO NAV';
  });

  // Save applicant id to localStorage session used by app (getCurrentApplicantId)
  await page.evaluate((id) => {
    localStorage.setItem('udyamone.applicant-id', id);
  }, seedRes.applicant_id);

  // Navigate to orders page
  await page.goto('http://127.0.0.1:3000/orders');
  await page.waitForTimeout(2500);
  out.ordersSnapshot = await ui.snapshot({ full: true });
  return out;
}
