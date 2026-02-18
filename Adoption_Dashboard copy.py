from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': '172.21.2.7',
    'database': 'finagg_prod',
    'user': 'aditya',
    'password': 'aditya@#$133#@##$$',
    'port': 3306
}

# CLEANED SQL QUERY - Removed all problematic backslashes and fixed spacing
# Reconstructed string to eliminate hidden whitespace/formatting characters
QUERY = (
    "WITH FameReportStatus AS ("
    "SELECT MID(gst_number, 3, 10) COLLATE utf8mb4_unicode_ci AS PAN, "
    "MAX(CASE WHEN data_json LIKE 'https://finagg-prod.s3.ap-south-1.amazonaws.com/fame-reports/%%' THEN 'Yes' ELSE 'No' END) AS Fame_Report_Present "
    "FROM fa_fame_report_data WHERE created_on >= %s GROUP BY PAN), "
    "AIPDStatus AS ("
    "SELECT pan_no COLLATE utf8mb4_unicode_ci AS PAN, "
    "MAX(CASE WHEN questions_json IS NOT NULL AND questions_json != '' THEN 'Yes' ELSE 'No' END) AS AI_PD_Attempted, "
    "MAX(CASE WHEN question_answer_json IS NOT NULL AND question_answer_json != '' THEN 'Yes' ELSE 'No' END) AS Answer_Attempted "
    "FROM fa_aipd_details GROUP BY pan_no COLLATE utf8mb4_unicode_ci), "
    "WhatsappStatus AS ("
    "SELECT DISTINCT loanRequestId FROM cbs_prodn.nfs_whatsapp_user_sessions "
    "WHERE created_on >= %s AND created_on < DATE_ADD(%s, INTERVAL 1 DAY) AND loanRequestId IS NOT NULL), "
    "BaseData AS ("
    "SELECT ffil.pan_no COLLATE utf8mb4_unicode_ci AS PAN, COALESCE(fo.org_name, ffil.enterprises_name) AS Firm_Name, "
    "tlrm.loan_request_id AS LOS_ID, CAST(AES_DECRYPT(tlrm.loan_request_no, 'Throttle Key') AS CHAR) AS LOS_Number, "
    "DATE(tlrm.created_on) AS LOS_Created_Date, DATE(ffil.created_on) AS Row_Invite_Date, fp.program_name AS Program_Name, "
    "tlrm.approval_status AS LOS_Approval_Status, CAST(AES_DECRYPT(tum.user_name, 'Throttle Key') AS CHAR) AS Invited_By_Raw, "
    "fssm.substatus_name AS Sub_Status_Name, "
    "CASE WHEN fp.program_name LIKE 'A%%' THEN 'Anchor' WHEN fp.program_name LIKE 'S%%' THEN 'SME' "
    "WHEN fp.program_name LIKE 'R%%' THEN 'Retail' ELSE 'Other' END AS Program_Category, "
    "CASE WHEN fp.program_name LIKE 'A %%' THEN SUBSTRING(fp.program_name, 3, 3) ELSE '-' END AS Anchor_Name "
    "FROM fa_fame_invite_log ffil "
    "LEFT JOIN fa_organisation fo ON ffil.pan_no COLLATE utf8mb4_unicode_ci = fo.pan_no COLLATE utf8mb4_unicode_ci "
    "LEFT JOIN ts_loan_request_master tlrm ON fo.org_Id = tlrm.org_Id "
    "LEFT JOIN ts_user_master tum ON tum.user_Id = ffil.created_by "
    "LEFT JOIN fa_program fp ON tlrm.program_id = fp.program_id "
    "LEFT JOIN fa_substatus_master fssm ON tlrm.substatus_id = fssm.id "
    "WHERE (ffil.created_on >= %s OR tlrm.created_on >= %s) "
    "UNION ALL "
    "SELECT fo.pan_no COLLATE utf8mb4_unicode_ci AS PAN, fo.org_name AS Firm_Name, tlrm.loan_request_id AS LOS_ID, "
    "CAST(AES_DECRYPT(tlrm.loan_request_no, 'Throttle Key') AS CHAR) AS LOS_Number, DATE(tlrm.created_on) AS LOS_Created_Date, "
    "NULL AS Row_Invite_Date, fp.program_name AS Program_Name, tlrm.approval_status AS LOS_Approval_Status, "
    "'Direct' AS Invited_By_Raw, fssm.substatus_name AS Sub_Status_Name, "
    "CASE WHEN fp.program_name LIKE 'A%%' THEN 'Anchor' WHEN fp.program_name LIKE 'S%%' THEN 'SME' ELSE 'Retail' END AS Program_Category, "
    "CASE WHEN fp.program_name LIKE 'A %%' THEN SUBSTRING(fp.program_name, 3, 3) ELSE '-' END AS Anchor_Name "
    "FROM ts_loan_request_master tlrm "
    "INNER JOIN fa_organisation fo ON tlrm.org_Id = fo.org_Id "
    "LEFT JOIN fa_fame_invite_log ffil ON fo.pan_no COLLATE utf8mb4_unicode_ci = ffil.pan_no COLLATE utf8mb4_unicode_ci "
    "LEFT JOIN fa_program fp ON tlrm.program_id = fp.program_id "
    "LEFT JOIN fa_substatus_master fssm ON tlrm.substatus_id = fssm.id "
    "WHERE ffil.id IS NULL AND tlrm.created_on >= %s), "
    "FinalRanking AS ("
    "SELECT bd.*, frs.Fame_Report_Present, aps.AI_PD_Attempted, aps.Answer_Attempted, "
    "MAX(CASE WHEN ws.loanRequestId IS NOT NULL THEN 1 ELSE 0 END) OVER (PARTITION BY bd.PAN) AS PAN_Has_Whatsapp, "
    "MAX(bd.Row_Invite_Date) OVER (PARTITION BY bd.PAN) AS Final_Invite_Date, "
    "FIRST_VALUE(bd.LOS_ID) OVER (PARTITION BY bd.PAN ORDER BY bd.LOS_Created_Date ASC) AS First_LOS_ID, "
    "FIRST_VALUE(bd.Invited_By_Raw) OVER (PARTITION BY bd.PAN ORDER BY bd.LOS_Created_Date ASC) AS Inherited_Invited_By, "
    "FIRST_VALUE(bd.Program_Name) OVER (PARTITION BY bd.PAN ORDER BY bd.LOS_Created_Date ASC) AS Parent_Prog, "
    "ROW_NUMBER() OVER (PARTITION BY bd.PAN ORDER BY bd.LOS_Created_Date DESC, bd.LOS_ID DESC) AS rn "
    "FROM BaseData bd "
    "LEFT JOIN FameReportStatus frs ON bd.PAN = frs.PAN "
    "LEFT JOIN AIPDStatus aps ON bd.PAN = aps.PAN "
    "LEFT JOIN WhatsappStatus ws ON bd.LOS_ID = ws.loanRequestId) "
    "SELECT *, "
    "CASE WHEN LOS_ID IS NULL THEN 'INVITE ONLY' WHEN LOS_ID = First_LOS_ID THEN 'PARENT' ELSE 'CHILD' END AS Relationship_Type, "
    "COALESCE(Inherited_Invited_By, 'System Generated') AS Invited_By, "
    "CASE WHEN Parent_Prog = 'Fame To Finagg Program' AND PAN_Has_Whatsapp = 1 THEN 'WhatsApp Onboarding' "
    "ELSE COALESCE(Inherited_Invited_By, 'System Generated') END AS Sourced_By "
    "FROM FinalRanking WHERE (rn = 1 OR LOS_ID IS NULL) "
    "AND ((LOS_Created_Date BETWEEN %s AND %s) OR (Final_Invite_Date BETWEEN %s AND %s))"
)

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Finagg Analytics - BI Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'IBM Plex Sans', sans-serif; background: #f8fafc; color: #0f172a; padding: 20px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        .header { display: flex; justify-content: space-between; align-items: center; background: white; padding: 15px 30px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .controls { display: flex; gap: 20px; align-items: center; }
        .toggle-container { display: flex; align-items: center; gap: 8px; font-size: 11px; font-weight: 600; color: #64748b; }

        /* Switch UI */
        .switch { position: relative; display: inline-block; width: 34px; height: 18px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #cbd5e1; transition: .4s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 12px; width: 12px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: #4f46e5; }
        input:checked + .slider:before { transform: translateX(16px); }

        .date-box { display: flex; gap: 12px; align-items: flex-end; }
        .input-group { display: flex; flex-direction: column; font-size: 10px; font-weight: 600; color: #64748b; }
        input[type="date"] { padding: 6px; border: 1px solid #cbd5e1; border-radius: 6px; font-family: 'IBM Plex Mono'; font-size: 12px; }

        .btn { background: #4f46e5; color: white; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13px; display: flex; align-items: center; gap: 8px; transition: 0.2s; }
        .btn:hover { background: #4338ca; }
        .btn:disabled { background: #94a3b8; cursor: not-allowed; }
        .btn-spinner { width: 12px; height: 12px; border: 2px solid #fff; border-top: 2px solid transparent; border-radius: 50%; animation: spin 0.6s linear infinite; display: none; }

        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; }
        .card { background: white; padding: 15px 20px; border-radius: 12px; border: 1px solid #e2e8f0; cursor: pointer; transition: 0.2s; }
        .card:hover { border-color: #4f46e5; transform: translateY(-2px); }
        .val { font-family: 'IBM Plex Mono'; font-size: 26px; font-weight: 600; display: block; color: #1e293b; }

        .details-section { background: white; margin-top: 25px; padding: 25px; border-radius: 12px; border: 1px solid #e2e8f0; display: none; position: relative; min-height: 500px; }
        .section-overlay { display: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.9); z-index: 999; border-radius: 12px; justify-content: center; align-items: center; }
        .section-overlay.active { display: flex; }
        .big-spinner { width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; }

        .table-container { overflow: visible; margin-top: 15px; }
        .scroll-wrapper { overflow-x: auto; overflow-y: visible; border: 1px solid #e2e8f0; border-radius: 8px; max-height: 600px; position: relative; }
        
        table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; white-space: nowrap; table-layout: auto; }
        th { text-align: left; padding: 12px; background: #f8fafc; border-bottom: 2px solid #e2e8f0; color: #475569; position: sticky; top: 0; z-index: 20; background-clip: padding-box; }
        td { padding: 12px; border-bottom: 1px solid #f1f5f9; font-family: 'IBM Plex Mono'; background: white; }
        
        /* Specific column stability */
        th, td { min-width: 120px; }
        th:first-child, td:first-child { min-width: 140px; position: sticky; left: 0; z-index: 21; border-right: 1px solid #e2e8f0; }
        td:first-child { background: #fdfdfd; }

        /* Improved Filter Styles */
        .filter-container { position: relative; width: 100%; }
        .filter-trigger { padding: 6px 10px; background: white; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 10px; cursor: pointer; text-align: left; color: #64748b; font-weight: 500; transition: all 0.2s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; min-width: 100px; display: flex; justify-content: space-between; align-items: center; }
        .filter-trigger::after { content: ' \25BC'; font-size: 8px; opacity: 0.5; }
        .filter-trigger:hover { border-color: #4f46e5; color: #4f46e5; box-shadow: 0 0 0 2px rgba(79,70,229,0.05); }
        .filter-trigger.active { border-color: #4f46e5; background: #eef2ff; color: #4f46e5; font-weight: 600; }
        
        .filter-dropdown { position: fixed; width: 220px; max-height: 300px; background: white; border: 1px solid #e2e8f0; border-radius: 10px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1); z-index: 9999; display: none; padding: 0; overflow: hidden; }
        .filter-dropdown.show { display: block; }
        .filter-dropdown .search-box { width: calc(100% - 16px); padding: 8px 10px; margin: 8px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 11px; font-family: 'IBM Plex Sans', sans-serif; outline: none; }
        .filter-dropdown .search-box:focus { border-color: #4f46e5; }
        .filter-dropdown .select-all-item { display: flex; align-items: center; gap: 8px; padding: 7px 12px; font-size: 11px; font-weight: 600; color: #4f46e5; border-bottom: 1px solid #e2e8f0; background: #f8fafc; cursor: pointer; }
        .filter-dropdown .filter-items-list { max-height: 200px; overflow-y: auto; padding: 4px 0; }
        .filter-item { display: flex; align-items: center; gap: 8px; padding: 6px 12px; font-size: 11px; cursor: pointer; }
        .filter-item:hover { background: #f1f5f9; }
        .filter-item input[type="checkbox"] { accent-color: #4f46e5; cursor: pointer; }
        
        .status-yes { color: #10b981; font-weight: 600; }
        .status-no { color: #ef4444; font-weight: 600; }

        .vpn-banner { display: none; background: #fee2e2; color: #991b1b; padding: 10px 20px; border-radius: 8px; border: 1px solid #fca5a5; margin-bottom: 20px; font-size: 13px; font-weight: 600; align-items: center; gap: 10px; }
        .vpn-banner.active { display: flex; }
        .vpn-dot { width: 8px; height: 8px; background: #ef4444; border-radius: 50%; }

    </style>
</head>
<body>
    <div class="vpn-banner" id="vpnBanner">
        <div class="vpn-dot"></div>
        <span>Database Disconnected: Please ensure you are connected to OpenVPN using <code>adityagcp.ovpn</code>.</span>
    </div>
    <div class="header">
        <div><h2>Finagg Onboarding</h2></div>
        <div class="controls">
            <div class="toggle-container">
                AUTO REFRESH (5m)
                <label class="switch">
                    <input type="checkbox" id="autoRefresh">
                    <span class="slider"></span>
                </label>
            </div>
            <div class="date-box">
                <div class="input-group">START <input type="date" id="start"></div>
                <div class="input-group">END <input type="date" id="end"></div>
                <button class="btn" id="analyzeBtn" onclick="loadDash()">
                    <div class="btn-spinner" id="btnSpinner"></div>
                    <span id="btnText">Analyze</span>
                </button>
            </div>
        </div>
    </div>

    <div class="grid" id="grid"></div>

    <div class="details-section" id="details">
        <div class="section-overlay" id="tableLoader"><div class="big-spinner"></div></div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3 id="detTitle" style="font-size: 18px; color: #1e293b;">Details View (Total: <span id="detCount">0</span>)</h3>
            <div style="display: flex; gap: 10px;">
                <button class="btn" style="background:#f43f5e" onclick="resetFilters()">Reset Filters</button>
                <button class="btn" style="background:#10b981" onclick="exportCSV()">Export CSV</button>
                <button class="btn" style="background:#64748b" onclick="document.getElementById('details').style.display='none'">Close</button>
            </div>
        </div>
        <div class="table-container">
            <div class="scroll-wrapper" id="scrollWrapper">
                <table>
                    <thead>
                        <tr id="detHead"></tr>
                        <tr id="filter-row"></tr>
                    </thead>
                    <tbody id="detBody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const API_URL = window.location.origin + '/api';
        let currentData = [];
        let displayedData = [];
        let activeFilters = {};
        let currentSort = { col: null, dir: 'asc' };
        const COLUMNS = ['PAN', 'Firm_Name', 'LOS_ID', 'LOS_Created_Date', 'Invite_Date', 'LOS_Approval_Status', 'Sub_Status_Name', 'Program_Name', 'Program_Category', 'Anchor_Name', 'Relationship_Type', 'Invited_By', 'Sourced_By', 'AI_PD_Attempted', 'Answer_Attempted', 'Fame_Report_Present'];

        window.onload = () => {
            const today = new Date().toISOString().split('T')[0];
            document.getElementById('start').value = today;
            document.getElementById('end').value = today;
            document.getElementById('filter-row').innerHTML = COLUMNS.map(c => `<td><div class="filter-container" id="f-${c}"></div></td>`).join('');
            loadDash();
            setInterval(() => { if(document.getElementById('autoRefresh').checked) loadDash(); }, 300000);
        };

        async function loadDash() {
            const btn = document.getElementById('analyzeBtn');
            const spinner = document.getElementById('btnSpinner');
            const txt = document.getElementById('btnText');
            btn.disabled = true; spinner.style.display = 'block'; txt.innerText = 'Processing...';

            try {
                const res = await fetch(API_URL + '/dashboard', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({start_date: document.getElementById('start').value, end_date: document.getElementById('end').value})
                });
                const data = await res.json();
                
                const vpnBanner = document.getElementById('vpnBanner');
                if (data.db_connected === false) {
                    vpnBanner.classList.add('active');
                } else {
                    vpnBanner.classList.remove('active');
                }

                renderCards(data.metrics.total);
            } catch(e) { console.error(e); } finally {
                btn.disabled = false; spinner.style.display = 'none'; txt.innerText = 'Analyze';
            }
        }

        function renderCards(m) {
            const conf = [
                {k:'total_onboarded', l:'Total Onboarded'}, {k:'fresh_onboarding', l:'Fresh Onboarding'},
                {k:'fame_to_finagg', l:'Fame to Finagg Cases'}, {k:'anchor', l:'Anchor Cases'},
                {k:'sme', l:'SME Cases'}, {k:'retail', l:'Retail Cases'},
                {k:'whatsapp', l:'WhatsApp'}, {k:'ai_pd', l:'AI PD'}, 
                {k:'ai_pd_answered', l:'AI Answered'}, {k:'fame_score', l:'Fame Consented'}
            ];
            document.getElementById('grid').innerHTML = conf.map(c => `
                <div class="card" onclick="loadDetails('${c.k}', '${c.l}')">
                    <small style="font-size: 10px; color: #64748b; font-weight:600;">${c.l}</small>
                    <span class="val">${(m[c.k] || 0).toLocaleString()}</span>
                </div>
            `).join('');
        }

        async function loadDetails(type, label) {
            const loader = document.getElementById('tableLoader');
            document.getElementById('details').style.display = 'block';
            loader.classList.add('active');
            try {
                const res = await fetch(API_URL + '/details', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({metric_type: type, start_date: document.getElementById('start').value, end_date: document.getElementById('end').value})
                });
                const result = await res.json();
                currentData = result.data || [];
                displayedData = [...currentData];
                activeFilters = {};
                document.getElementById('detTitle').innerText = label;
                generateFilters();
                renderTable(currentData);
            } catch(e) { console.error(e); } finally { loader.classList.remove('active'); }
        }

        function generateFilters() {
            COLUMNS.forEach(col => {
                const container = document.getElementById('f-' + col);
                const uniqueValues = [...new Set(currentData.map(item => item[col] || '-'))].sort();
                container.innerHTML = `
                    <div class="filter-trigger" onclick="toggleDropdown('${col}')">Select...</div>
                    <div class="filter-dropdown" id="dd-${col}">
                        <input type="text" class="search-box" placeholder="\u{1F50D} Search..." onkeyup="filterList('${col}', this)">
                        <label class="select-all-item">
                            <input type="checkbox" onchange="toggleSelectAll('${col}', this)"> Select All
                        </label>
                        <div class="filter-items-list">
                            ${uniqueValues.map(val => `<label class="filter-item"><input type="checkbox" value="${val}" onchange="updateFilters('${col}')"> ${val}</label>`).join('')}
                        </div>
                    </div>
                `;
            });
        }

        function toggleDropdown(col) {
            const dropdown = document.getElementById('dd-' + col);
            const trigger = document.querySelector(`#f-${col} .filter-trigger`);
            const isShowing = dropdown.classList.contains('show');
            
            // Close all first
            document.querySelectorAll('.filter-dropdown').forEach(d => d.classList.remove('show'));
            
            if (!isShowing) {
                const rect = trigger.getBoundingClientRect();
                dropdown.style.top = (rect.bottom + 5) + 'px';
                dropdown.style.left = rect.left + 'px';
                dropdown.classList.add('show');
                
                // Adjust if overflowing viewport
                const ddRect = dropdown.getBoundingClientRect();
                if (ddRect.right > window.innerWidth) {
                    dropdown.style.left = (window.innerWidth - ddRect.width - 20) + 'px';
                }
            }
        }

        function toggleSelectAll(col, selectAllCheckbox) {
            const checkboxes = document.querySelectorAll(`#dd-${col} .filter-items-list input[type="checkbox"]`);
            checkboxes.forEach(cb => { cb.checked = selectAllCheckbox.checked; });
            updateFilters(col);
        }

        function updateFilters(col) {
            const selected = Array.from(document.querySelectorAll(`#dd-${col} .filter-items-list input:checked`)).map(cb => cb.value);
            const allCheckboxes = document.querySelectorAll(`#dd-${col} .filter-items-list input[type="checkbox"]`);
            const selectAllCb = document.querySelector(`#dd-${col} .select-all-item input[type="checkbox"]`);
            if (selectAllCb) { selectAllCb.checked = selected.length === allCheckboxes.length && allCheckboxes.length > 0; }
            if(selected.length > 0) {
                activeFilters[col] = selected;
                const trigger = document.querySelector(`#f-${col} .filter-trigger`);
                trigger.classList.add('active');
                trigger.textContent = selected.length === 1 ? selected[0] : `${selected.length} selected`;
            } else {
                delete activeFilters[col];
                const trigger = document.querySelector(`#f-${col} .filter-trigger`);
                trigger.classList.remove('active');
                trigger.textContent = 'Select...';
            }
            displayedData = currentData.filter(row => Object.keys(activeFilters).every(key => activeFilters[key].includes(row[key] || '-')));
            renderTable(displayedData);
        }

        function renderTable(data) {
            const head = document.getElementById('detHead');
            const body = document.getElementById('detBody');
            
            head.innerHTML = `<tr>${COLUMNS.map(c => {
                let indicator = '';
                if (currentSort.col === c) {
                    indicator = currentSort.dir === 'asc' ? ' \u2191' : ' \u2193';
                }
                return `<th onclick="sortTable('${c}')" style="cursor:pointer; white-space:nowrap;">${c.replace(/_/g, ' ')}${indicator}</th>`;
            }).join('')}</tr>`;
            
            body.innerHTML = data.map(row => `<tr>${COLUMNS.map(c => {
                const val = row[c] || '-';
                let cls = '';
                if (val === 'Yes') cls = 'status-yes';
                if (val === 'No') cls = 'status-no';
                return `<td class="${cls}">${val}</td>`;
            }).join('')}</tr>`).join('');
            document.getElementById('detCount').innerText = data.length;
        }

        function sortTable(col) {
            if (currentSort.col === col) {
                currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.col = col;
                currentSort.dir = 'asc';
            }
            
            displayedData.sort((a, b) => {
                let v1 = a[col] || '';
                let v2 = b[col] || '';
                
                // Handle numeric/date strings if needed, but localeCompare is generally safe for these strings
                let res = String(v1).localeCompare(String(v2), undefined, {numeric: true, sensitivity: 'base'});
                return currentSort.dir === 'asc' ? res : -res;
            });
            
            renderTable(displayedData);
        }

        function filterList(col, input) {
            const val = input.value.toLowerCase();
            document.querySelectorAll(`#dd-${col} .filter-item`).forEach(it => { it.style.display = it.textContent.toLowerCase().includes(val) ? 'flex' : 'none'; });
        }

        function resetFilters() {
            activeFilters = {};
            document.querySelectorAll('.filter-dropdown input').forEach(i => i.checked = false);
            document.querySelectorAll('.filter-trigger').forEach(t => { t.classList.remove('active'); t.textContent = 'Select...'; });
            displayedData = [...currentData];
            renderTable(displayedData);
        }

        function exportCSV() {
            const csvRows = [COLUMNS.join(',')];
            displayedData.forEach(r => csvRows.push(COLUMNS.map(c => `"${r[c]||'-'}"`).join(',')));
            const blob = new Blob([csvRows.join('\n')], {type: 'text/csv'});
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'data.csv'; a.click();
        }

        window.onclick = (e) => { 
            if (!e.target.matches('.filter-trigger') && !e.target.closest('.filter-dropdown')) {
                document.querySelectorAll('.filter-dropdown').forEach(d => d.classList.remove('show'));
            }
        };

        // Close dropdowns on scroll to prevent they stay floating incorrectly
        document.addEventListener('scroll', (e) => {
            if (e.target.closest && (e.target.id === 'scrollWrapper' || e.target === document)) {
                document.querySelectorAll('.filter-dropdown').forEach(d => d.classList.remove('show'));
            }
        }, true);
    </script>
</body>
</html>
"""


def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        logger.error(f"DB Connect Error: {e}")
        return None


def check_db_connectivity():
    conn = get_db_connection()
    if conn:
        conn.close()
        return True
    return False


def execute_query(query, params=None):
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params) if params else cursor.execute(query)
        return cursor.fetchall()
    except Error as e:
        logger.error(f"Query Error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_params(start, end):
    return (start, start, end, start, start, start, start, end, start, end)


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/dashboard', methods=['POST'])
def get_dashboard_data():
    db_connected = check_db_connectivity()
    try:
        data = request.get_json()
        res = execute_query(QUERY, get_params(data['start_date'], data['end_date']))
        if res is None: return jsonify({'metrics': {'total': {}}, 'db_connected': db_connected}), 200

        unique_pans = {k: set() for k in
                       ['onboarded', 'fresh_onboarding', 'fame_to_finagg', 'retail', 'sme', 'anchor', 'whatsapp', 'ai_pd', 'ai_pd_answered', 'fame']}
        metrics = {'invite_only': 0}

        for row in res:
            pan = row.get('PAN')
            rel = row.get('Relationship_Type', '')
            cat = row.get('Program_Category', '')
            if rel in ['PARENT', 'CHILD']: unique_pans['onboarded'].add(pan)
            if rel == 'INVITE ONLY': metrics['invite_only'] += 1
            if cat == 'Retail': unique_pans['retail'].add(pan)
            if cat == 'SME': unique_pans['sme'].add(pan)
            if cat == 'Anchor': unique_pans['anchor'].add(pan)
            if row.get('Sourced_By') == 'WhatsApp Onboarding': unique_pans['whatsapp'].add(pan)
            if row.get('AI_PD_Attempted') == 'Yes': unique_pans['ai_pd'].add(pan)
            if row.get('Answer_Attempted') == 'Yes': unique_pans['ai_pd_answered'].add(pan)
            if row.get('Fame_Report_Present') == 'Yes': unique_pans['fame'].add(pan)

            # Fresh Onboarding: Both LOS_Created_Date and Invite_Date must be within date range
            start_date = data['start_date']
            end_date = data['end_date']
            los_created_date = row.get('LOS_Created_Date')
            invite_date_val = row.get('Final_Invite_Date')
            if isinstance(los_created_date, date):
                los_created_date_str = los_created_date.strftime('%Y-%m-%d')
            else:
                los_created_date_str = str(los_created_date) if los_created_date else None
            if isinstance(invite_date_val, date):
                invite_date_str = invite_date_val.strftime('%Y-%m-%d')
            else:
                invite_date_str = str(invite_date_val) if invite_date_val else None

            if (los_created_date_str and invite_date_str
                    and start_date <= los_created_date_str <= end_date
                    and start_date <= invite_date_str <= end_date):
                unique_pans['fresh_onboarding'].add(pan)

            # Fame to Finagg: Program Name is 'Fame To Finagg Program'
            if row.get('Program_Name') == 'Fame To Finagg Program':
                unique_pans['fame_to_finagg'].add(pan)

        metrics.update({
            'total_onboarded': len(unique_pans['onboarded']),
            'fresh_onboarding': len(unique_pans['fresh_onboarding']),
            'fame_to_finagg': len(unique_pans['fame_to_finagg']),
            'retail': len(unique_pans['retail']),
            'sme': len(unique_pans['sme']),
            'anchor': len(unique_pans['anchor']),
            'whatsapp': len(unique_pans['whatsapp']),
            'ai_pd': len(unique_pans['ai_pd']),
            'ai_pd_answered': len(unique_pans['ai_pd_answered']),
            'fame_score': len(unique_pans['fame'])
        })
        return jsonify({'metrics': {'total': metrics}, 'db_connected': db_connected})
    except Exception as e:
        logger.error(f"Dash Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/details', methods=['POST'])
def get_details():
    try:
        data = request.get_json()
        raw_res = execute_query(QUERY, get_params(data['start_date'], data['end_date']))
        m_type = data['metric_type']
        if raw_res is None: return jsonify({'data': [], 'count': 0})

        filtered = []
        seen = set()
        for r in raw_res:
            match = False
            rel = r.get('Relationship_Type', '')
            cat = r.get('Program_Category', '')
            if m_type == 'total_onboarded' and rel in ['PARENT', 'CHILD']:
                match = True
            elif m_type == 'anchor' and cat == 'Anchor':
                match = True
            elif m_type == 'sme' and cat == 'SME':
                match = True
            elif m_type == 'retail' and cat == 'Retail':
                match = True
            elif m_type == 'fresh_onboarding':
                start_date = data['start_date']
                end_date = data['end_date']
                los_created_date = r.get('LOS_Created_Date')
                invite_date_val = r.get('Final_Invite_Date')
                los_str = los_created_date.strftime('%Y-%m-%d') if isinstance(los_created_date, (date, datetime)) else None
                inv_str = invite_date_val.strftime('%Y-%m-%d') if isinstance(invite_date_val, (date, datetime)) else None
                match = (los_str is not None and inv_str is not None
                         and start_date <= los_str <= end_date
                         and start_date <= inv_str <= end_date)
            elif m_type == 'fame_to_finagg' and r.get('Program_Name') == 'Fame To Finagg Program':
                match = True
            elif m_type == 'invite_only' and rel == 'INVITE ONLY':
                match = True
            elif m_type == 'whatsapp' and r.get('Sourced_By') == 'WhatsApp Onboarding':
                match = True
            elif m_type == 'ai_pd' and r.get('AI_PD_Attempted') == 'Yes':
                match = True
            elif m_type == 'ai_pd_answered' and r.get('Answer_Attempted') == 'Yes':
                match = True
            elif m_type == 'fame_score' and r.get('Fame_Report_Present') == 'Yes':
                match = True

            if match and r.get('PAN') not in seen:
                seen.add(r.get('PAN'))
                r['Invite_Date'] = r.get('Final_Invite_Date')
                for k, v in r.items():
                    if isinstance(v, (datetime, date)): r[k] = v.strftime('%d %b %Y')
                filtered.append(r)
        return jsonify({'data': filtered, 'count': len(filtered)})
    except Exception as e:
        logger.error(f"Details Error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*50)
    print("FINAGG ADOPTION DASHBOARD STARTUP")
    print("="*50)
    if check_db_connectivity():
        print("DATABASE STATUS: CONNECTED \u2705")
    else:
        print("DATABASE STATUS: DISCONNECTED \u274C")
        print("ACTION REQUIRED: Please connect to OpenVPN using 'adityagcp.ovpn'")
    print("="*50 + "\n")
    
    app.run(debug=False, host='0.0.0.0', port=8088)
