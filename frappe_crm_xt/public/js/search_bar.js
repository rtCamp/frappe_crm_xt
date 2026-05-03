/*
 * frappe_crm_xt — global search bar
 *
 * Adds a Cmd/Ctrl+K modal to the FCRM frontend, backed by frappe_search.
 * Pure DOM/CSS so it can be dropped in via <script> without participating
 * in FCRM's Vue build.
 *
 * Hits: frappe_search.api.search.get_global_search_results
 * Doctypes: CRM Lead, CRM Deal, Contact, CRM Task, FCRM Note (override
 *   via window.crm_xt_search_doctypes if you want a different set).
 */
(function () {
	"use strict";

	const DEFAULT_DOCTYPES = ["CRM Lead", "CRM Deal", "Contact", "CRM Task", "FCRM Note"];

	const ROUTE_BY_DOCTYPE = {
		"CRM Lead": (name) => `/crm/leads/${encodeURIComponent(name)}`,
		"CRM Deal": (name) => `/crm/deals/${encodeURIComponent(name)}`,
		Contact: (name) => `/crm/contacts/${encodeURIComponent(name)}`,
		"CRM Task": (name) => `/crm/tasks/${encodeURIComponent(name)}`,
		"FCRM Note": (name) => `/crm/notes/${encodeURIComponent(name)}`,
	};

	let modalEl, inputEl, resultsEl, hintEl;
	let lastQuery = "";
	let inflight = null;

	function getCsrfToken() {
		return window.csrf_token || (window.boot && window.boot.csrf_token) || "";
	}

	function getAllowedDoctypes() {
		return Array.isArray(window.crm_xt_search_doctypes) && window.crm_xt_search_doctypes.length
			? window.crm_xt_search_doctypes
			: DEFAULT_DOCTYPES;
	}

	function injectStyles() {
		if (document.getElementById("crm-xt-search-styles")) return;
		const style = document.createElement("style");
		style.id = "crm-xt-search-styles";
		style.textContent = `
			.crm-xt-overlay { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 9999;
				display: none; align-items: flex-start; justify-content: center; padding-top: 12vh; }
			.crm-xt-overlay.is-open { display: flex; }
			.crm-xt-modal { width: min(640px, 92vw); background: #fff; border-radius: 10px;
				box-shadow: 0 20px 60px rgba(0,0,0,.25); overflow: hidden; font: 14px/1.4 system-ui, sans-serif; }
			.crm-xt-input-wrap { display: flex; align-items: center; padding: 10px 14px;
				border-bottom: 1px solid #e5e7eb; }
			.crm-xt-input { flex: 1; border: 0; outline: 0; font-size: 16px; background: transparent; }
			.crm-xt-hint { font-size: 11px; color: #94a3b8; margin-left: 12px; white-space: nowrap; }
			.crm-xt-results { max-height: 60vh; overflow-y: auto; }
			.crm-xt-row { display: block; padding: 10px 14px; border-bottom: 1px solid #f1f5f9;
				cursor: pointer; color: inherit; text-decoration: none; }
			.crm-xt-row:hover, .crm-xt-row.is-active { background: #f8fafc; }
			.crm-xt-row .doctype { font-size: 11px; color: #64748b; text-transform: uppercase;
				letter-spacing: .04em; margin-bottom: 2px; }
			.crm-xt-row .title { color: #0f172a; font-weight: 500; }
			.crm-xt-row .ctx { color: #475569; font-size: 12px; margin-top: 2px;
				display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
			.crm-xt-empty { padding: 18px 14px; color: #64748b; text-align: center; }
		`;
		document.head.appendChild(style);
	}

	function buildModal() {
		modalEl = document.createElement("div");
		modalEl.className = "crm-xt-overlay";
		modalEl.innerHTML = `
			<div class="crm-xt-modal" role="dialog" aria-label="Search">
				<div class="crm-xt-input-wrap">
					<input class="crm-xt-input" type="text" placeholder="Search leads, deals, contacts…" autocomplete="off" />
					<span class="crm-xt-hint">esc</span>
				</div>
				<div class="crm-xt-results"></div>
			</div>
		`;
		document.body.appendChild(modalEl);

		inputEl = modalEl.querySelector(".crm-xt-input");
		resultsEl = modalEl.querySelector(".crm-xt-results");
		hintEl = modalEl.querySelector(".crm-xt-hint");

		modalEl.addEventListener("click", (e) => {
			if (e.target === modalEl) close();
		});
		inputEl.addEventListener("input", onInput);
		inputEl.addEventListener("keydown", onKey);
	}

	function open() {
		injectStyles();
		if (!modalEl) buildModal();
		modalEl.classList.add("is-open");
		inputEl.value = "";
		resultsEl.innerHTML = `<div class="crm-xt-empty">Type at least 3 characters…</div>`;
		setTimeout(() => inputEl.focus(), 0);
	}

	function close() {
		if (modalEl) modalEl.classList.remove("is-open");
		lastQuery = "";
	}

	function onKey(e) {
		if (e.key === "Escape") {
			e.preventDefault();
			close();
		} else if (e.key === "Enter") {
			const active = resultsEl.querySelector(".crm-xt-row.is-active") ||
				resultsEl.querySelector(".crm-xt-row");
			if (active) {
				e.preventDefault();
				active.click();
			}
		} else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
			e.preventDefault();
			moveActive(e.key === "ArrowDown" ? 1 : -1);
		}
	}

	function moveActive(delta) {
		const rows = Array.from(resultsEl.querySelectorAll(".crm-xt-row"));
		if (!rows.length) return;
		let idx = rows.findIndex((r) => r.classList.contains("is-active"));
		idx = (idx + delta + rows.length) % rows.length;
		rows.forEach((r) => r.classList.remove("is-active"));
		rows[idx].classList.add("is-active");
		rows[idx].scrollIntoView({ block: "nearest" });
	}

	let debounceTimer = null;
	function onInput() {
		const q = inputEl.value.trim();
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => runSearch(q), 180);
	}

	function runSearch(query) {
		if (query === lastQuery) return;
		lastQuery = query;
		if (query.length < 3) {
			resultsEl.innerHTML = `<div class="crm-xt-empty">Type at least 3 characters…</div>`;
			return;
		}
		if (inflight) inflight.abort();
		const ctrl = new AbortController();
		inflight = ctrl;

		const params = new URLSearchParams();
		params.set("text", query);
		params.set("start", "0");
		params.set("limit", "20");
		getAllowedDoctypes().forEach((d) => params.append("allowed_doctypes", d));

		fetch("/api/method/frappe_search.api.search.get_global_search_results", {
			method: "POST",
			credentials: "same-origin",
			signal: ctrl.signal,
			headers: {
				"Content-Type": "application/x-www-form-urlencoded",
				"X-Frappe-CSRF-Token": getCsrfToken(),
				Accept: "application/json",
			},
			body: params.toString(),
		})
			.then((r) => r.json())
			.then((data) => {
				if (lastQuery !== query) return; // stale
				renderResults(data && data.message);
			})
			.catch((err) => {
				if (err.name === "AbortError") return;
				resultsEl.innerHTML = `<div class="crm-xt-empty">Search failed.</div>`;
			});
	}

	function renderResults(payload) {
		const list = (payload && (payload.results || payload)) || [];
		if (!Array.isArray(list) || !list.length) {
			resultsEl.innerHTML = `<div class="crm-xt-empty">No results.</div>`;
			return;
		}
		resultsEl.innerHTML = "";
		list.forEach((row, i) => {
			const a = document.createElement("a");
			a.className = "crm-xt-row" + (i === 0 ? " is-active" : "");
			const route = (ROUTE_BY_DOCTYPE[row.doctype] || ((n) => `/app/${row.doctype.toLowerCase().replace(/\s+/g, "-")}/${encodeURIComponent(n)}`))(row.name);
			a.href = route;
			a.innerHTML = `
				<div class="doctype">${escapeHtml(prettyDoctype(row.doctype))}</div>
				<div class="title">${escapeHtml(row.title || row.name)}</div>
				${row.content ? `<div class="ctx">${escapeHtml(stripTags(row.content)).slice(0, 220)}</div>` : ""}
			`;
			a.addEventListener("click", (e) => {
				e.preventDefault();
				close();
				navigate(route);
			});
			resultsEl.appendChild(a);
		});
	}

	function navigate(route) {
		// FCRM is a Vue SPA — push a history entry instead of full reload.
		try {
			window.history.pushState({}, "", route);
			window.dispatchEvent(new PopStateEvent("popstate"));
		} catch (_) {
			window.location.href = route;
		}
	}

	function prettyDoctype(dt) {
		// Trim leading "CRM " for display — lets the bridge-aware variant in
		// activities feel consistent (Lead, Deal, Contact).
		return dt && dt.indexOf("CRM ") === 0 ? dt.slice(4) : dt;
	}

	function escapeHtml(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function stripTags(s) {
		return String(s == null ? "" : s).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
	}

	function onGlobalKey(e) {
		const isToggle = (e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey);
		if (isToggle) {
			e.preventDefault();
			if (modalEl && modalEl.classList.contains("is-open")) close();
			else open();
		}
	}

	function init() {
		document.addEventListener("keydown", onGlobalKey);
		window.crm_xt_search = { open, close };
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
