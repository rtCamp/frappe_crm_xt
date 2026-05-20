// Auto-pull CRM Deal products and currency into the Quotation form when
// the user lands on /app/quotation/new?quotation_to=CRM Deal&crm_deal=<deal>&...
//
// `get_quotation_url`
// (crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings) sends the
// user from the CRM "Create Quotation" button to /app/quotation/new with
// the `crm_deal` query param pre-set. Standard ERPNext has no
// `make_quotation`-equivalent for CRM Deal, so items and currency are
// left blank. Call our `update_missing_values` helper once on form load
// when the form is new and `crm_deal` is populated. The Opportunity
// counterpart lives in rtCamp/crm_erp_bridge
// (public/js/quotation_auto_items.js).
//
// Bound to `onload_post_render` (not `onload` or `refresh`) so URL params
// have already been merged into frm.doc and we don't re-trigger on every
// re-render. A per-form flag (`frm.__deal_values_pulled`) guards against
// duplicate invocations and is reset on error so the user can retry.

frappe.ui.form.on("Quotation", {
	onload_post_render(frm) {
		if (!frm.is_new()) return;
		if (frm.__deal_values_pulled) return;
		if (!frm.doc.crm_deal) return;
		frm.__deal_values_pulled = true;

		frappe.call({
			method: "frappe_crm_xt.api.quotation.update_missing_values",
			args: { source_name: frm.doc.crm_deal },
			callback: (r) => {
				const src = r.message;
				if (!src) return;

				if (src.currency && src.currency !== frm.doc.currency) {
					frm.set_value("currency", src.currency);
				}

				if (Array.isArray(src.items) && src.items.length) {
					frm.clear_table("items");
					src.items.forEach((row) => {
						frm.add_child("items", row);
					});
					frm.refresh_field("items");
					frm.cscript.calculate_taxes_and_totals();
				}

				frm.dirty();
			},
			error: (e) => {
				// Reset the flag so the user can manually click
				// "Get Items From" without our flag blocking a retry.
				frm.__deal_values_pulled = false;
				console.warn("[frappe_crm_xt] auto-fetch CRM Deal values failed", e);
			},
		});
	},
});
