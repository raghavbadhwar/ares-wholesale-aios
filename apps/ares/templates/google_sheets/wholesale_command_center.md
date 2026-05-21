# Ares Wholesale Command Center Sheet

Tabs and minimum columns:

- Dashboard: metric, value, updated_at
- Customers: id, name, aliases, phone, gstin, location, credit_limit, payment_terms, preferred_language, notes, status
- Products: id, name, aliases, category, unit, current_stock, reorder_level, supplier_id, buying_price, selling_price, margin
- Orders: id, customer_id, source, raw_text, items, requested_delivery_date, status, confidence, assigned_staff, created_at, updated_at
- Invoices: id, invoice_number, customer_id, date, amount, taxable_value, tax_amount, gst_rate_percent, cgst_amount, sgst_amount, igst_amount, cess_amount, place_of_supply, reverse_charge, invoice_type, ecommerce_gstin, line_items, due_date, status, source_file
- Payments: id, customer_id, amount, date, mode, reference, matched_invoice_id, confidence, status
- Stock: sku_id, name, current_stock, reorder_level, unit, supplier_id, sales_velocity, last_updated
- Suppliers: id, name, aliases, phone, lead_time_days, notes
- Tasks: id, title, owner, due_at, status, source
- Approvals: id, type, client_id, proposed_action, data, reason, source, confidence, risk_level, status, created_at, decided_at, decided_by
- Business Rules: id, category, description, sensitive, created_at
- Memory Notes: id, category, subject_id, content, confidence, source, sensitive, created_at, updated_at, expires_at
- Workflow Runs: id, workflow_name, client_id, status, started_at, ended_at, inputs, outputs, errors
