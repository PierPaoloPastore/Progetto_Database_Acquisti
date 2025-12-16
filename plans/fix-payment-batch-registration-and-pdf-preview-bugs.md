# fix: Payment Batch Registration and PDF Preview Bugs

## Overview

This plan addresses two critical bugs in the payment management system that prevent users from registering batch payments and previewing PDF documents:

1. **Bug #1 (Critical)**: "Registra pagamento multiplo" (batch payment registration) fails when user clicks submit
2. **Bug #2 (High)**: PDF preview doesn't appear in right-side viewer after selecting a PDF file

Both bugs were discovered through comprehensive codebase analysis that revealed:
- **Root Cause #1**: ID type mismatch - UI sends Document IDs but backend expects Payment IDs
- **Root Cause #2**: iframe `srcdoc` attribute conflicts with dynamically setting `src` attribute
- **Additional Critical Issues**: Status enum case inconsistency and missing validation

## Problem Statement

### Bug #1: Batch Payment Registration Failure

**User Impact**: Users cannot register payments for multiple invoices at once, forcing them to register each payment individually - a significant productivity loss.

**Technical Cause**: The batch payment form iterates over `Document` objects and sends `doc.id` values, but the backend service expects `payment.id` values. When the service tries to look up Payment records using Document IDs, it fails with a "Payment not found" error or silently fails.

**Data Flow Breakdown**:
```
Frontend (inbox.html:139) → sends Document IDs via name="payment_id"
    ↓
Backend (routes_payments.py:103) → receives as selected_payments
    ↓
Service (payment_service.py:133) → calls uow.payments.get_by_id(document_id)
    ↓
Result: Payment not found → ERROR
```

**Severity**: CRITICAL - Core feature completely broken, blocks essential workflow

### Bug #2: PDF Preview Not Working

**User Impact**: Users cannot preview uploaded payment PDFs before submitting, reducing confidence in uploaded files and increasing errors.

**Technical Cause**: The iframe element has a `srcdoc` attribute with placeholder HTML. When JavaScript dynamically sets the `src` attribute with a blob URL, browsers prioritize `srcdoc` over `src`, causing the placeholder to remain visible instead of showing the PDF.

**Code Location**:
- Template: `app/templates/payments/inbox.html:172-179`
- JavaScript: `app/static/js/payments.js:47-62`

**Severity**: HIGH - Feature completely broken, degrades user experience significantly

### Additional Critical Issue Discovered: Status Enum Case Mismatch

During analysis, a critical data consistency bug was discovered:

**Technical Cause**: `payment_service.py` uses uppercase status values (`'PARTIAL'`, `'PAID'`) but the Payment model defines lowercase enum values (`'partial'`, `'paid'`, `'unpaid'`, `'overdue'`).

**Impact**: This causes the `document.is_paid` calculation to always fail because the comparison `p.status == "PAID"` will never match when the actual value is `"paid"`.

**Severity**: CRITICAL - Affects data integrity, incorrect payment statuses shown to users

## Proposed Solution

### Phase 1: Fix Critical Bugs (MVP)

#### 1.1 Fix Bug #1: Document ID → Payment ID Mapping

**Approach**: Keep the Document-based UI (minimal refactor) but add backend logic to convert Document IDs to Payment IDs.

**Why this approach**:
- Minimal changes to existing UI
- Maintains user familiarity with current interface
- Can be implemented quickly
- Preserves existing data-search and filtering logic

**Implementation**:
1. Modify `/payments/batch` route to accept Document IDs
2. For each Document ID, query all associated Payment records with `status IN ('unpaid', 'partial')`
3. If no Payment records exist for a Document, auto-create them with:
   - `due_date` = Document.due_date (or today if null)
   - `expected_amount` = amount user entered
   - `status` = 'unpaid'
4. Process batch payment using Payment records

**Files to Modify**:
- `app/web/routes_payments.py` (batch_payment route)
- `app/repositories/payment_repo.py` (add get_unpaid_by_document_ids method)
- `app/services/payment_service.py` (modify create_batch_payment to handle Documents)

#### 1.2 Fix Bug #2: Remove srcdoc Attribute

**Approach**: Remove the `srcdoc` attribute from iframe and handle placeholder via CSS/JavaScript.

**Why this approach**:
- Simplest fix with no additional dependencies
- Maintains current iframe-based preview (no PDF.js needed)
- Works across all modern browsers
- Progressive enhancement friendly

**Implementation**:
1. Remove `srcdoc` attribute from iframe element
2. Add initial placeholder div inside preview container
3. JavaScript shows/hides placeholder based on file selection
4. Add fallback message if browser blocks PDF in iframe

**Files to Modify**:
- `app/templates/payments/inbox.html` (iframe structure)
- `app/static/js/payments.js` (setupPdfPreview function)
- `app/static/css/payments.css` (placeholder styling)

#### 1.3 Fix Status Enum Case Inconsistency

**Approach**: Update service layer to use lowercase enum values matching the database schema.

**Why this approach**:
- Aligns with model definition and database constraints
- Fixes downstream bugs in is_paid calculation
- Minimal code changes

**Implementation**:
1. Find all occurrences of uppercase status strings in `payment_service.py`
2. Replace with lowercase equivalents
3. Update comparison logic for is_paid calculation

**Files to Modify**:
- `app/services/payment_service.py` (lines 142-146, 161)

### Phase 2: Add Validation and Error Handling

#### 2.1 Amount Validation

**Add validation rules**:
- Amount must be > 0
- Amount must not exceed 999,999,999.99 (database limit)
- Amount must have maximum 2 decimal places
- Warning if amount > Payment.expected_amount (potential overpayment)

**Implementation**:
- Client-side: HTML5 constraints + JavaScript validation
- Server-side: Validation in route handler before service call

#### 2.2 File Upload Validation

**Add validation rules**:
- File type must be PDF (verify MIME type, not just extension)
- File size must not exceed 10MB
- Handle upload interruptions gracefully

**Implementation**:
- Client-side: File size check before upload, MIME type validation
- Server-side: Content-type header validation, werkzeug file size check

#### 2.3 Improved Error Messages

**Current**: Generic flash message "Errore durante il pagamento cumulativo"

**Improved**: Specific error messages for each failure:
- "Pagamento per fattura #123 (Fornitore XYZ): Payment record non trovato"
- "Pagamento per fattura #124: Importo non valido (deve essere > 0)"
- "PDF upload fallito: File troppo grande (max 10MB)"

**Implementation**:
- Collect errors per-payment during batch processing
- Return list of errors instead of failing on first error
- Display errors with document context

### Phase 3: Testing and Validation

#### 3.1 Manual Testing Checklist

- [ ] Batch payment with single Document succeeds
- [ ] Batch payment with multiple Documents succeeds
- [ ] Batch payment with Document that has no Payment records auto-creates Payment
- [ ] Batch payment with partial amounts sets status to 'partial'
- [ ] Batch payment with full amounts sets status to 'paid'
- [ ] Document.is_paid correctly reflects payment status
- [ ] PDF preview shows PDF in iframe
- [ ] PDF preview handles large files gracefully
- [ ] PDF preview shows fallback for non-PDF files
- [ ] Error messages are specific and actionable
- [ ] Italian decimal format (comma) handled correctly

#### 3.2 Edge Cases to Test

- [ ] User selects Documents but enters zero amounts → should show validation error
- [ ] User selects Documents but deselects before submit → should handle gracefully
- [ ] User uploads 20MB PDF → should show file size error
- [ ] User uploads .doc file despite accept="application/pdf" → should reject
- [ ] User pays partial amount → Payment.status should be 'partial'
- [ ] User pays amount exceeding expected_amount → should warn but allow
- [ ] Multiple Payments for single Document → should process all selected
- [ ] Network interruption during upload → should handle gracefully

## Technical Considerations

### Architecture Impacts

**Repository Pattern**: All database queries must go through repositories (per CLAUDE.md requirement)
- Add new method: `PaymentRepository.get_unpaid_by_document_ids(document_ids: List[int]) -> List[Payment]`
- This method returns all Payment records with status IN ('unpaid', 'partial') for given Documents

**Unit of Work Pattern**: Batch payment must use single transaction for consistency
- If any Payment fails, entire batch rolls back
- PaymentDocument creation included in same transaction
- Document.is_paid updates included in same transaction

**Single Table Inheritance**: Documents table uses discriminator column
- Batch payment should work with all document types (invoice, F24, insurance, etc.)
- Filter by document_type if needed (currently filters to invoices only)

### Security Considerations

**File Upload Security**:
- ALWAYS use `secure_filename()` to sanitize filenames
- Validate MIME type server-side (don't trust client)
- Set MAX_CONTENT_LENGTH in config to prevent DoS
- Store files outside web root to prevent direct access
- Generate unique filenames to prevent overwrites

**Input Validation**:
- Validate all numeric inputs server-side (amounts, IDs)
- Use parameterized queries (SQLAlchemy handles this)
- Sanitize user-provided notes/descriptions

**CSRF Protection**:
- Ensure all forms include CSRF token
- Current implementation uses Flask's built-in CSRF (not Flask-WTF)
- Verify token validation is enabled in middleware

### Performance Implications

**Database Queries**:
- Current: N queries (one per selected Document)
- Improved: 1 bulk query with `WHERE document_id IN (...)`
- Use `get_unpaid_by_document_ids()` to fetch all Payments in single query

**File Upload**:
- PDF files can be large (5-10MB typical)
- Use streaming upload if files exceed memory limits
- Consider adding upload progress indicator (future enhancement)

**PDF Preview**:
- Blob URLs keep file in memory until revoked
- Add `URL.revokeObjectURL()` when user selects new file
- Prevents memory leaks with multiple file selections

### Data Model Considerations

**Payment-Document Relationship**:
- Current schema: Payment has FK to Document (N:1)
- One Document can have multiple Payment records (installments, multiple due dates)
- Batch payment processes Payment records, not Documents directly

**Payment Status Enum** (from model):
```python
status = db.Column(
    db.Enum('unpaid', 'planned', 'pending', 'partial', 'paid', 'cancelled', 'overdue'),
    nullable=False,
    default='unpaid'
)
```

**Validation Rules**:
- Status transitions: unpaid → partial → paid (typical flow)
- Status can be set to 'cancelled' by user action
- Status should become 'overdue' if due_date < today and status IN ('unpaid', 'partial')

## Acceptance Criteria

### Bug #1: Batch Payment Registration

- [ ] User can select one or more Documents (invoices) from the table
- [ ] User can enter payment amounts for each selected Document
- [ ] User can optionally upload a PDF payment document
- [ ] User can select payment method from dropdown
- [ ] User clicks "Registra Pagamento Multiplo" button
- [ ] System processes batch payment successfully
- [ ] System creates PaymentDocument record if PDF uploaded
- [ ] System updates Payment records with paid amounts and dates
- [ ] System sets Payment.status to 'paid' if amount ≥ expected_amount
- [ ] System sets Payment.status to 'partial' if amount < expected_amount
- [ ] System updates Document.is_paid flag correctly
- [ ] User sees success message with count of processed payments
- [ ] If any Payment fails, user sees specific error message with document context

### Bug #2: PDF Preview

- [ ] User clicks "Allega PDF di pagamento" file input
- [ ] User selects PDF file from filesystem
- [ ] System displays PDF preview in right-side iframe immediately
- [ ] Preview shows actual PDF content (not placeholder)
- [ ] If browser blocks PDF, system shows fallback message
- [ ] User can see PDF before submitting form
- [ ] If user selects different file, preview updates accordingly
- [ ] If user clears file selection, placeholder returns

### Status Enum Fix

- [ ] Payment.status values are lowercase in database
- [ ] Payment.status comparisons use lowercase strings
- [ ] Document.is_paid calculation correctly identifies paid documents
- [ ] Payment list views show correct status labels
- [ ] Filtering by status works correctly

## Success Metrics

**Functional Success**:
- Batch payment registration completes without errors
- PDF preview displays on all major browsers (Chrome, Firefox, Edge, Safari)
- Payment status accurately reflects payment state
- Document.is_paid flag accurately reflects when all payments complete

**Data Integrity**:
- No orphaned Payment records created
- No duplicate PaymentDocument records
- Status values match enum definition
- Transaction rollback works on errors

**User Experience**:
- Users can register batch payments in < 30 seconds
- Error messages provide clear guidance for resolution
- PDF preview appears within 1 second of file selection
- No data loss on validation errors

## Dependencies & Risks

### Dependencies

**Required Before Implementation**:
- [ ] Database schema review: Confirm Payment.status enum values
- [ ] Repository pattern: Ensure PaymentRepository exists and follows conventions
- [ ] Unit of Work: Confirm transaction handling for batch operations

**Optional (for testing)**:
- [ ] Sample PDF files of various sizes (1MB, 5MB, 10MB, 15MB)
- [ ] Sample Documents with different payment configurations
- [ ] Browser compatibility testing environment

### Risks & Mitigation

**Risk 1: Data Migration Needed for Existing Status Values**
- **Impact**: If database contains uppercase status values, fix will break existing data
- **Mitigation**: Run migration query to lowercase all status values BEFORE deploying code changes
- **SQL**: `UPDATE payments SET status = LOWER(status) WHERE status IN ('PAID', 'PARTIAL', 'UNPAID')`

**Risk 2: Performance Degradation with Large Batches**
- **Impact**: Processing 50+ payments at once could timeout or lock database
- **Mitigation**: Add batch size limit (max 25 payments per batch), use optimized bulk queries
- **Fallback**: If timeout occurs, show error suggesting smaller batches

**Risk 3: Browser Compatibility for PDF Preview**
- **Impact**: Some browsers/configs block PDF rendering in iframes
- **Mitigation**: Add feature detection, show download link as fallback
- **Code**: Check `previewFrame.contentDocument` after load to detect block

**Risk 4: Concurrent Payment Registration**
- **Impact**: Two users registering payment for same Document simultaneously
- **Mitigation**: Use database-level locking or optimistic concurrency control
- **Note**: Current code doesn't handle this - add to future enhancement backlog

## Implementation Plan

### Step 1: Fix Status Enum Case (30 minutes)

**Why first**: Quick fix, unblocks other work, prevents data corruption

1. Search for all uppercase status strings in `payment_service.py`
2. Replace with lowercase equivalents
3. Test status comparisons manually
4. Run server and verify no errors

**Files**: `app/services/payment_service.py`

### Step 2: Fix PDF Preview (1 hour)

**Why second**: Independent of other bugs, quick win for UX

1. Remove `srcdoc` attribute from iframe in `inbox.html`
2. Add placeholder div with CSS class
3. Update `setupPdfPreview()` to show/hide placeholder
4. Add error handling for blocked PDFs
5. Test on Chrome, Firefox, Edge

**Files**:
- `app/templates/payments/inbox.html`
- `app/static/js/payments.js`
- `app/static/css/payments.css`

### Step 3: Add Payment Repository Method (1 hour)

**Why third**: Required for batch payment fix

1. Add `get_unpaid_by_document_ids(document_ids: List[int])` method
2. Implement query: `SELECT * FROM payments WHERE document_id IN (...) AND status IN ('unpaid', 'partial')`
3. Write docstring with usage example
4. Test query with sample data

**Files**: `app/repositories/payment_repo.py`

### Step 4: Fix Batch Payment Logic (3 hours)

**Why fourth**: Most complex change, requires Steps 1-3 complete

1. Modify `batch_payment()` route to handle Document IDs
2. Call new repository method to fetch Payment records
3. Auto-create Payment records if missing (edge case)
4. Update `create_batch_payment()` service method
5. Add per-payment error collection
6. Update flash messages for clarity
7. Test with various scenarios

**Files**:
- `app/web/routes_payments.py`
- `app/services/payment_service.py`

### Step 5: Add Validation (2 hours)

**Why fifth**: Improves robustness after core functionality works

1. Add client-side amount validation (JavaScript)
2. Add server-side amount validation (route handler)
3. Add file upload validation (size, type)
4. Add error display logic (per-field errors)
5. Test validation with invalid inputs

**Files**:
- `app/web/routes_payments.py`
- `app/static/js/payments.js`
- `app/templates/payments/inbox.html`

### Step 6: Testing & Documentation (2 hours)

**Why last**: Verify all changes work together

1. Run through manual testing checklist
2. Test edge cases
3. Update `docs/LESSONS.md` with findings
4. Add comments to modified code
5. Prepare demo for stakeholders

**Total Estimated Time**: 9.5 hours (1.5 days)

## References & Research

### Internal References

**Critical Files** (with line numbers):
- `app/web/routes_payments.py:96-127` - batch_payment route (Bug #1 location)
- `app/services/payment_service.py:87-165` - create_batch_payment (service logic)
- `app/templates/payments/inbox.html:83-181` - Payment form UI
- `app/static/js/payments.js:47-62` - PDF preview setup (Bug #2 location)
- `app/models/payment.py:51-105` - Payment model definition
- `app/repositories/payment_repo.py` - Payment data access layer

**Architecture Documentation**:
- `CLAUDE.md` - Project conventions and mandatory patterns
- `docs/architecture.md` - Layer structure and patterns
- `docs/database.md` - Schema reference and source of truth rules
- `docs/LESSONS.md` - Known pitfalls and lessons learned

**Related Features**:
- Single payment registration: `routes_payments.py:22-95`
- Payment document import: `payment_service.py:167-236`
- Document detail view: `routes_documents.py:detail_view`

### External References

**Flask Documentation**:
- [Handling File Uploads - Flask Docs](https://flask.palletsprojects.com/en/stable/patterns/fileuploads/)
- [Form Validation with WTForms](https://flask.palletsprojects.com/en/stable/patterns/wtforms/)
- [Flask Error Handling](https://betterstack.com/community/guides/scaling-python/flask-error-handling/)

**JavaScript/Browser APIs**:
- [FormData API - MDN](https://developer.mozilla.org/en-US/docs/Web/API/FormData)
- [File API - MDN](https://developer.mozilla.org/en-US/docs/Web/API/File)
- [URL.createObjectURL() - MDN](https://developer.mozilla.org/en-US/docs/Web/API/URL/createObjectURL)
- [Constraint Validation API - MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Constraint_validation)

**Best Practices**:
- [Flask Security Best Practices 2025](https://hub.corgea.com/articles/flask-security-best-practices-2025)
- [Preventing Double Form Submissions](https://www.bram.us/2020/11/04/preventing-double-form-submissions/)
- [Client-side form validation - MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/Form_validation)

**PDF Preview**:
- [Preview PDFs During Upload with Javascript](https://usefulangle.com/post/87/javascript-preview-pdf-during-upload)
- [How to show PDF file upload previews using JavaScript](https://www.thatsoftwaredude.com/content/13936/how-to-show-pdf-file-upload-previews-using-javascript)

### Related Issues/PRs

**Recent Payment Module Changes**:
- Commit `783bdef`: "fix: change batch payment status from 'processed' to 'reconciled'" (Dec 15, 2025)
- Commit `28f6e6b`: Revert of payments refactor (Dec 15, 2025)
- Commit `3d68917`: "feat(payments): refactor UI to split-view and add batch payment logic" (Dec 12, 2025)

**Lessons Learned** (from `docs/LESSONS.md`):
- Internal mapping: Decouple function arguments from DB field names when they diverge
- Name mismatch risk: Ensure template names match route render_template calls
- Cleanup: Remove old templates during refactoring to avoid "Stale UI"

## Pseudo Code Examples

### Example 1: Enhanced batch_payment Route

```python
# app/web/routes_payments.py

@payments_bp.route("/batch", methods=["POST"])
def batch_payment():
    """Register batch payment on multiple documents."""
    # Get form data
    file = request.files.get("file")
    method = request.form.get("method") or request.form.get("payment_method")
    notes = request.form.get("notes")

    # Get selected DOCUMENT IDs (not Payment IDs - this is the key change)
    selected_doc_ids = request.form.getlist("payment_id")  # Renamed for clarity

    # Validate input
    if not selected_doc_ids:
        flash("Seleziona almeno un documento da pagare.", "warning")
        return redirect(url_for("payments.inbox_view"))

    # Build allocations from amounts
    doc_allocations = []  # List of {document_id, amount}
    for doc_id in selected_doc_ids:
        raw_amount = (request.form.get(f"amount_{doc_id}") or "0").replace(",", ".")
        try:
            amount = float(raw_amount)
        except ValueError:
            flash(f"Importo non valido per documento {doc_id}", "warning")
            return redirect(url_for("payments.inbox_view"))

        if amount <= 0:
            continue

        doc_allocations.append({"document_id": int(doc_id), "amount": amount})

    if not doc_allocations:
        flash("Inserisci almeno un importo > 0.", "warning")
        return redirect(url_for("payments.inbox_view"))

    # Process batch payment (service layer handles Document → Payment mapping)
    try:
        with UnitOfWork() as uow:
            payment_service = PaymentService(uow)
            results = payment_service.create_batch_payment_from_documents(
                file=file,
                document_allocations=doc_allocations,
                method=method,
                notes=notes
            )
            uow.commit()

        # Display results
        success_count = len([r for r in results if r['success']])
        error_count = len([r for r in results if not r['success']])

        if success_count > 0:
            flash(f"{success_count} pagamenti registrati con successo.", "success")

        if error_count > 0:
            for result in results:
                if not result['success']:
                    flash(f"Errore per documento {result['document_id']}: {result['error']}", "danger")

    except Exception as exc:
        app.logger.exception(f"Batch payment failed: {exc}")
        flash(f"Errore durante il pagamento cumulativo: {exc}", "danger")

    return redirect(url_for("payments.inbox_view"))
```

### Example 2: New Service Method

```python
# app/services/payment_service.py

def create_batch_payment_from_documents(
    self,
    file,
    document_allocations: List[Dict],  # [{"document_id": 123, "amount": 500.00}, ...]
    method: str,
    notes: str = None
) -> List[Dict]:
    """
    Process batch payment for multiple documents.
    Auto-creates Payment records if they don't exist.

    Returns:
        List of dicts: [{"document_id": 123, "success": True, "payment_id": 456}, ...]
    """
    results = []

    # Step 1: Create PaymentDocument if file provided
    payment_document = None
    if file and file.filename:
        payment_document = self._create_payment_document_from_file(file, "reconciled")

    # Step 2: Get all Document IDs
    doc_ids = [alloc["document_id"] for alloc in document_allocations]

    # Step 3: Fetch all Payment records for these Documents (NEW METHOD)
    payment_map = {}  # {document_id: [Payment, ...]}
    payments = self.uow.payments.get_unpaid_by_document_ids(doc_ids)
    for payment in payments:
        if payment.document_id not in payment_map:
            payment_map[payment.document_id] = []
        payment_map[payment.document_id].append(payment)

    # Step 4: Process each document allocation
    for alloc in document_allocations:
        doc_id = alloc["document_id"]
        amount = alloc["amount"]

        try:
            # Get or create Payment record
            if doc_id not in payment_map or len(payment_map[doc_id]) == 0:
                # Auto-create Payment record (edge case handling)
                document = self.uow.documents.get_by_id(doc_id)
                if not document:
                    results.append({"document_id": doc_id, "success": False, "error": "Documento non trovato"})
                    continue

                payment = Payment(
                    document_id=doc_id,
                    due_date=document.due_date or datetime.now().date(),
                    expected_amount=amount,
                    status='unpaid'
                )
                self.uow.payments.add(payment)
            else:
                # Use first unpaid/partial Payment
                payment = payment_map[doc_id][0]

            # Update Payment record
            payment.paid_date = datetime.now().date()
            payment.paid_amount = amount
            payment.payment_method = method
            payment.notes = notes
            payment.payment_document = payment_document

            # Set status
            if amount >= payment.expected_amount:
                payment.status = 'paid'  # Lowercase!
            else:
                payment.status = 'partial'  # Lowercase!

            # Update Document.is_paid flag
            document = self.uow.documents.get_by_id(doc_id)
            related_payments = self.uow.payments.get_by_document_id(doc_id)
            document.is_paid = all(p.status == 'paid' for p in related_payments)  # Lowercase comparison!

            results.append({"document_id": doc_id, "success": True, "payment_id": payment.id})

        except Exception as e:
            app.logger.error(f"Failed to process payment for doc {doc_id}: {e}")
            results.append({"document_id": doc_id, "success": False, "error": str(e)})

    return results
```

### Example 3: New Repository Method

```python
# app/repositories/payment_repo.py

def get_unpaid_by_document_ids(self, document_ids: List[int]) -> List[Payment]:
    """
    Fetch all unpaid/partial Payment records for given Document IDs.

    Args:
        document_ids: List of Document IDs to query

    Returns:
        List of Payment objects with status IN ('unpaid', 'partial')

    Example:
        >>> repo.get_unpaid_by_document_ids([123, 124, 125])
        [Payment(id=456, document_id=123, status='unpaid'), ...]
    """
    return db.session.query(Payment).filter(
        Payment.document_id.in_(document_ids),
        Payment.status.in_(['unpaid', 'partial'])
    ).all()
```

### Example 4: Fixed PDF Preview JavaScript

```javascript
// app/static/js/payments.js

function setupPdfPreview() {
    const fileInput = document.getElementById("pdf-file");
    const previewFrame = document.getElementById("pdf-preview");
    const placeholderDiv = document.getElementById("pdf-placeholder");

    if (!fileInput || !previewFrame || !placeholderDiv) {
        console.warn("PDF preview elements not found");
        return;
    }

    fileInput.addEventListener("change", () => {
        const file = fileInput.files[0];

        // Validate file
        if (!file) {
            // No file selected - show placeholder
            previewFrame.removeAttribute("src");
            placeholderDiv.classList.remove("d-none");
            return;
        }

        // Validate file type
        if (file.type !== 'application/pdf') {
            alert('Solo file PDF sono consentiti.');
            fileInput.value = '';
            return;
        }

        // Validate file size (10MB limit)
        const maxSize = 10 * 1024 * 1024;
        if (file.size > maxSize) {
            alert('File troppo grande. Massimo 10MB consentito.');
            fileInput.value = '';
            return;
        }

        // Create blob URL and display
        const url = URL.createObjectURL(file);
        previewFrame.src = url;
        placeholderDiv.classList.add("d-none");

        // Clean up old blob URL when new file selected
        previewFrame.addEventListener('load', () => {
            URL.revokeObjectURL(url);
        }, { once: true });

        // Fallback if PDF blocked by browser
        setTimeout(() => {
            try {
                // Check if PDF loaded successfully
                const doc = previewFrame.contentDocument;
                if (!doc || doc.body.innerHTML === '') {
                    // Browser blocked PDF rendering
                    placeholderDiv.innerHTML = `
                        <p class="text-center text-muted">
                            <i class="bi bi-exclamation-triangle"></i><br>
                            Anteprima non disponibile nel browser.<br>
                            <a href="${url}" download="${file.name}" class="btn btn-sm btn-primary mt-2">
                                Scarica PDF
                            </a>
                        </p>
                    `;
                    placeholderDiv.classList.remove("d-none");
                }
            } catch (e) {
                // Cross-origin error (expected for blob URLs)
                // PDF likely loaded successfully
                console.debug('PDF preview loaded (cross-origin check blocked)');
            }
        }, 500);
    });
}
```

### Example 5: Updated Template Structure

```html
<!-- app/templates/payments/inbox.html (partial) -->

<!-- File upload section -->
<div class="col-lg-6">
    <label for="pdf-file" class="form-label">Allega PDF di pagamento</label>
    <input type="file" name="file" id="pdf-file" accept="application/pdf" class="form-control">
    <div class="form-text">Il PDF verrà visualizzato nell'anteprima a destra.</div>
</div>

<!-- PDF Preview section (FIXED) -->
<div class="split-section card">
    <div class="card-header bg-white border-bottom-0 d-flex align-items-center">
        <h5 class="mb-0">Anteprima PDF</h5>
    </div>
    <div class="card-body position-relative">
        <!-- Placeholder (shown when no file selected) -->
        <div id="pdf-placeholder" class="preview-placeholder">
            <p class="text-center text-muted py-5">
                <i class="bi bi-file-earmark-pdf fs-1"></i><br>
                Carica un PDF per visualizzarlo qui.
            </p>
        </div>

        <!-- Iframe (NO srcdoc attribute!) -->
        <iframe id="pdf-preview" class="preview-frame" title="Anteprima PDF"></iframe>
    </div>
</div>
```

## Todo List Format (for /workflows:work)

```markdown
## Phase 1: Critical Bug Fixes

- [ ] Fix status enum case inconsistency in payment_service.py
  - [ ] Search for uppercase 'PAID' and replace with 'paid'
  - [ ] Search for uppercase 'PARTIAL' and replace with 'partial'
  - [ ] Update is_paid calculation to use lowercase comparison
  - [ ] Test status updates manually

- [ ] Fix PDF preview (remove srcdoc conflict)
  - [ ] Remove srcdoc attribute from iframe in inbox.html
  - [ ] Add placeholder div with id="pdf-placeholder"
  - [ ] Update setupPdfPreview() to show/hide placeholder
  - [ ] Add file validation (type, size)
  - [ ] Add fallback for blocked PDFs
  - [ ] Test on Chrome, Firefox, Edge

- [ ] Add Payment repository method
  - [ ] Implement get_unpaid_by_document_ids(document_ids)
  - [ ] Write query with IN clause and status filter
  - [ ] Add docstring with example
  - [ ] Test with sample data

- [ ] Fix batch payment Document→Payment mapping
  - [ ] Rename route logic to clarify Document IDs used
  - [ ] Call get_unpaid_by_document_ids() to fetch Payments
  - [ ] Add logic to auto-create Payments if missing
  - [ ] Update service method create_batch_payment_from_documents()
  - [ ] Add per-payment error collection
  - [ ] Update flash messages for clarity
  - [ ] Test with single document
  - [ ] Test with multiple documents
  - [ ] Test with document having no payments

## Phase 2: Validation & Error Handling

- [ ] Add amount validation
  - [ ] Client-side: Add JavaScript validation for amounts
  - [ ] Server-side: Validate amount > 0, <= 999999999.99
  - [ ] Server-side: Validate 2 decimal places max
  - [ ] Add warning for overpayment (amount > expected_amount)
  - [ ] Test with invalid amounts

- [ ] Add file upload validation
  - [ ] Client-side: Check file size before upload
  - [ ] Client-side: Validate MIME type
  - [ ] Server-side: Verify Content-Type header
  - [ ] Server-side: Check file size against MAX_CONTENT_LENGTH
  - [ ] Test with large files, non-PDF files

- [ ] Improve error messages
  - [ ] Collect errors per-payment in service layer
  - [ ] Return structured error results
  - [ ] Display errors with document context
  - [ ] Test error display with intentional failures

## Phase 3: Testing & Documentation

- [ ] Run manual testing checklist
  - [ ] Test all scenarios from Acceptance Criteria
  - [ ] Test all edge cases listed in plan
  - [ ] Verify on multiple browsers

- [ ] Update documentation
  - [ ] Add findings to docs/LESSONS.md
  - [ ] Add comments to modified code
  - [ ] Update CLAUDE.md if patterns changed
```

---

**Plan Created**: 2025-12-16
**Estimated Implementation Time**: 9.5 hours (1.5 days)
**Priority**: CRITICAL (P0)
**Complexity**: Medium (requires backend + frontend + data model changes)
