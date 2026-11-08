# Demonstration Runbook & Evaluator Walkthrough

**Product**: UdyamOne  
**Competition**: Airtel SYNC 2026 (Track A: Project Udyam Digital)  
**Team**: PulseForge  
**Target Audience**: Competition Judges, Technical Evaluators, Live Demonstration Team  

---

## 1. Demonstration Environment Checklist

Before starting a live evaluation or recording a demonstration video, ensure the following prerequisites are met:

- [ ] **Python Backend Running**: Accessible at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) returning `{"status": "ok"}`.
- [ ] **Next.js Frontend Running**: Accessible at [http://127.0.0.1:3000](http://127.0.0.1:3000).
- [ ] **Prototype Accounts Configured**: Valid JSON accounts in `UDYAMONE_KYC_AUTH_USERS` representing all four roles:
  - `CUSTOMER` (e.g. `customer_demo`)
  - `REVIEWER` (e.g. `reviewer_demo`)
  - `OPERATIONS` (e.g. `ops_demo`)
  - `PARTNER` (e.g. `partner_demo`)
- [ ] **Signing Secret Set**: Minimum 32 bytes in `UDYAMONE_KYC_AUTH_SECRET`.
- [ ] **Clean Browser Context**: Use separate browser profiles, private/incognito windows, or clear session storage between role transitions to observe role-based navigation updates.

---

## 2. End-to-End Live Walkthrough Script

### Step 1: MSME Discovery & Guided Business Profile
1. Navigate to [http://127.0.0.1:3000](http://127.0.0.1:3000). Highlight the UdyamOne landing page and its guided MSME onboarding experience.
2. Click **Get started** (navigates to `/get-started`).
3. Fill in business attributes:
   - **Business Name**: `PulseForge Retail Enterprises`
   - **Business Type**: `Micro retail`
   - **City**: `Mumbai` (Tier 1)
   - **Employees**: `5`
   - **Sites**: `1`
   - **Primary Requirements**: Check `High-speed connectivity` and `Cloud productivity`.
4. Click **Save and view recommendations**.
5. *Evaluator Note*: The platform generates a persistent applicant ID (e.g., `APPL-...`) and computes tailored bundle recommendations (Budget, Recommended, Advanced).

---

### Step 2: Quotation Preview
1. On the recommendation view, examine the recommended products (e.g., Business Fibre 200 Mbps, Cloud Office Standard).
2. Adjust quantities if desired and click **Preview quote**.
3. Highlight the transparent pricing summary:
   - Estimated monthly recurring price range (e.g., `₹2,499 – ₹2,899/mo`).
   - One-time setup fees (e.g., `₹1,000`).
   - Line-item breakdown and contract terms.
4. *Evaluator Note*: This quote is persisted in SQLite as an authoritative preview for this applicant.

---

### Step 3: Smart KYC & Synthetic Registry Verification
1. Navigate to **Smart KYC** via the top navigation bar (`/kyc`).
2. Sign in as the `CUSTOMER` account (`customer_demo`).
3. Point out the role badge: `Signed in as customer_demo · customer`.
4. **Consent Gate**: Read the document-processing notice. Check the confirmation box and click **Accept KYC consent**. Notice that upload and processing controls become active only after consent is recorded.
5. **Synthetic Registry Checks**: Click **Run synthetic registry checks**.
   - Review GSTIN Verification status (`VERIFIED` or `MISMATCH`).
   - Review Udyam Verification status (`VERIFIED` or `MISMATCH`).
   - Point out the synthetic data disclosure: *These checks query supplied competition datasets, not live government portals.*

---

### Step 4: Order Placement & Snapshot Creation
1. In the header navigation, click **My Orders** (navigates to `/orders`).
2. Point out that the page automatically loads the latest persisted quote generated in Step 2.
3. Review the pricing snapshot preview.
4. Check the mandatory prototype confirmation box:
   > *"I confirm I want to place this prototype order request. I understand pricing is estimated only and this is not a binding commercial offer or contract."*
5. Click **Confirm and place order**.
6. **Expected UI Outcome**:
   - Success banner appears: *"Order placed successfully!"*
   - A direct **View My Orders** button is displayed.
   - The order list displays the new order in status `ORDER_PLACED`.
   - The confirmed pricing snapshot is immutably rendered with line items and prototype terms.
7. Attempting to click the order placement button again or submitting twice is prevented by server-side duplicate prevention (HTTP 409).

---

### Step 5: Operations Partner Assignment
1. Open a new Incognito window or click **Sign out** and navigate to [http://127.0.0.1:3000/operations](http://127.0.0.1:3000/operations).
2. Sign in as `ops_demo` (`OPERATIONS` role).
3. The top navigation bar dynamically displays **Operations Dashboard**.
4. Use the status filter dropdown to select `Order placed`.
5. Locate the newly placed order and click **Manage order**.
6. Inspect the frozen pricing snapshot and initial event history.
7. Under **Partner assignment**:
   - Enter Partner Username: `partner_demo`
   - Enter Reason: `Zone coverage - Mumbai West`
   - Click **Assign partner**.
8. **Expected UI Outcome**:
   - Status updates immediately to `ASSIGNED`.
   - An event `STATUS_TRANSITION` (`ORDER_PLACED` → `ASSIGNED`) is appended to the timeline recording `ops_demo` as the actor.

---

### Step 6: Partner Fulfilment Workflow
1. In a separate window or after signing out, navigate to [http://127.0.0.1:3000/partner](http://127.0.0.1:3000/partner).
2. Sign in as `partner_demo` (`PARTNER` role).
3. The top navigation bar dynamically displays **Partner Workspace**.
4. The assigned order appears in the partner worklist. Click **Open fulfilment**.
5. Note that the partner has access only to assigned order details; sensitive KYC files and unrelated customer records are hidden.
6. Under **Update fulfilment progress**:
   - Select Next Status: `Fulfilment in progress`
   - Enter Progress Note: `Site survey completed; wiring scheduled.`
   - Click **Record update**.
7. Advance status again:
   - Select Next Status: `Fulfilment completed`
   - Enter Progress Note: `Hardware installed and physical loop tested.`
   - Click **Record update**.
8. Hand off to Operations:
   - Select Next Status: `Activation pending`
   - Click **Record update**.
9. *Security Check*: Point out that the partner dropdown does not contain `Activated`. Partners cannot activate orders directly.

---

### Step 7: Operations Simulated Activation
1. Return to the Operations session (`ops_demo`) at `/operations`.
2. Filter or search for `Activation pending` and open the order.
3. Under **Lifecycle transition**:
   - Select New Status: `Activated`
   - Enter Reason: `Simulated prototype activation completed.`
   - Click **Apply transition**.
4. **Expected UI Outcome**:
   - Status badge turns green: `Activated`.
   - The order enters a terminal state; further transition options are locked.
   - An audit event is appended recording `ops_demo` (Operations) and the exact activation timestamp.

---

### Step 8: Customer Tracking Verification
1. Return to the Customer session (`customer_demo`) at `/orders`.
2. Refresh the order view.
3. **Expected UI Outcome**:
   - Current status shows `Activated`.
   - Progress steps show all milestones completed.
   - Order Timeline displays the complete chronological audit trail from `ORDER_PLACED` to `ASSIGNED`, `FULFILMENT_IN_PROGRESS`, `FULFILMENT_COMPLETED`, `ACTIVATION_PENDING`, and `ACTIVATED` with full actor accountability.
   - The pricing snapshot remains identical to the initial quote.
   - Cancellation button is hidden (customers cannot cancel fulfilled or activated orders).

---

## 3. Case-Pack Synthetic Verification Scenarios (K01 vs. K07)

When demonstrating Smart KYC and registry verification with specimen data from `data/kyc_documents/`, observe these facts:

### A. Applicant K01 (Negative Mismatch Demonstration)
- **GSTIN Specimen**: `27AAACW1234F1Z5`
- **Synthetic Registry Status in `mock_gstin_registry.csv`**: Record exists but has `status = CANCELLED`.
- **Expected Outcome**: GSTIN verification reports `MISMATCH` (*"Registry record is not active (CANCELLED)"*).
- **Udyam Specimen**: Document omitted or missing valid registration number. Reports `MISMATCH` or `UNAVAILABLE`.
- **Demonstration Value**: This is a prototype matching exercise against a synthetic cancelled GSTIN record — it shows that UdyamOne surfaces registry status mismatches; it is not a statutory compliance determination.

### B. Applicant K07 (Positive Verification Demonstration)
- **Business Profile**: Neelgiri Physio Clinic (Sole Proprietorship, Delhi).
- **Udyam Specimen (`K07_udyam_certificate.png`)**:
  - Extracted Udyam Number: `UDYAM-DL-00-9565547`
  - Extracted Enterprise Name: `Neelgiri Physio Clinic`
  - Synthetic Registry (`mock_udyam_registry.csv`): Active record with enterprise name `Neelgiri Physio Clinic`, city `Delhi`, state `Delhi`.
  - **Udyam Matching & Outcome**:
    - When verified with applicant city `Delhi`, both `applicant_business_name` and `city` match the registry values (`neelgiri physio clinic` and `delhi`).
    - **Udyam Expected Outcome**: Reports `VERIFIED` (*"The unique Udyam record and available business details match the synthetic registry."*).
- **GSTIN Specimen (`K07_gst_certificate.png`)**:
  - Specimen Image Identifier: `07CPCXN0398P1ZT` (12th character is the numeral `1`, following standard GSTIN structure).
  - Synthetic Registry (`mock_gstin_registry.csv`): Active record with GSTIN `07CPCXN0398P1ZT`, legal name `Neha Banerjee (Prop. Neelgiri Physio Clinic)`, and trade name `Neelgiri Physio Clinic`.
  - **OCR Nuance & Human-in-the-Loop Correction**:
    - Local OCR on the specimen image may exhibit character ambiguity on the 12th position (reading letter `I` vs. numeral `1` or extracting legal name as `Neha Banerjee (Prop. Shri Physio Clinic)` due to font rendering).
    - In Smart KYC demonstrations, when the user corrects any OCR character ambiguity or legal name variance via the UI form (`PATCH /corrections`), the adjustment is saved with `correction_applied = true`.
    - The subsequent registry check runs against the corrected identifier and names, cleanly reporting `VERIFIED`.
- **Important Disclosure**: K07 reflects Neha Banerjee's Neelgiri Physio Clinic in Delhi across both the specimen images and the synthetic registry CSVs. The system demonstrates successful matching against the supplied synthetic Udyam registry (matching city `Delhi`) and the **auditability of human-in-the-loop manual corrections** for OCR ambiguities on GSTIN and legal name fields. A synthetic registry match is not official government verification.

---

## 2a. Manual walkthrough record (8 November 2026)

The core customer → operations → partner → customer flow was **manually demonstrated end-to-end on 8 November 2026** in a real browser (supported by screenshots): landing → onboarding → recommendations/bundles → AI advisor (EN/TE) → quote → KYC inspection (existing specimens, OCR values, prior corrections, consent record) → registry checks (observed GSTIN INCONCLUSIVE / Udyam MISMATCH) → order placement → Operations assignment → Partner fulfilment (In Progress → Completed → Activation Pending) → Operations simulated activation → customer verification of Activated status, snapshot, milestones and event history.

This is **human-operated testing**, distinct from automated headless browser testing (which remains out of scope). Not covered in that walkthrough: fresh consent/upload/OCR runs, a positive registry match, the Reviewer role, negative authorization scenarios in the browser, all error/empty/loading states, and full responsive testing.

---

## 4. Test Cleanup & Resetting State

All automated regression and API E2E scripts use isolated, temporary SQLite databases in the OS temp directory and do not alter the persistent development database.

If you wish to reset your local development database (`backend/data/applicants.sqlite3`):

```powershell
# Stop the backend server first
Remove-Item backend\data\applicants.sqlite3 -Force -ErrorAction SilentlyContinue
# Starting the backend will automatically re-create clean schema tables
```

*(Do not delete mock registries in `data/mock_registries/` or specimen documents in `data/kyc_documents/`).*

---

## 5. Technical Disclosures & Known Prototype Boundaries

1. **Synthetic Registries**: GSTIN and Udyam checks validate against competition mock CSVs. No real government portals are queried.
2. **Prototype Quotations**: Quotations are non-binding estimates. No payment processing, gateways, or commercial billing accounts are provisioned.
3. **Simulated Activation**: Activation transitions within the software state machine. No physical telecom provisioning or network element configuration occurs.
4. **Browser Testing Out of Scope (automation)**: Formal automated quality gates rely on backend pytest suites (**205 tests reported passing**, with 9 warnings in the reported run), previously verified isolated API E2E scripts (29/29 checks), frontend ESLint, and Next.js production builds. Headless browser automation was not executed. Separately, a **human-operated core walkthrough was completed on 8 November 2026** (see §2a); its coverage limits are listed there.