const state = { csrf: '', username: '', page: 'dashboard', searchTimer: null, options: { patients: [], doctors: [], departments: [] } };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const pages = {
  patients: {
    title: 'Patients', description: 'Manage patient profiles and registration information.', resource: 'patients', add: 'Add patient',
    fields: [
      ['full_name', 'Full name', 'text', true], ['age', 'Age', 'number', true],
      ['gender', 'Gender', 'select', true, ['Female', 'Male', 'Other']], ['phone', 'Phone number', 'tel', true],
      ['blood_group', 'Blood group', 'select', false, ['', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']],
      ['registration_date', 'Registration date', 'date', false], ['address', 'Address', 'textarea', false, null, true]
    ],
    columns: [['patient_code', 'Patient ID'], ['full_name', 'Patient'], ['age', 'Age'], ['gender', 'Gender'], ['phone', 'Phone'], ['registration_date', 'Registered']]
  },
  doctors: {
    title: 'Doctors', description: 'Manage clinicians, specialties, and department assignments.', resource: 'doctors', add: 'Add doctor',
    fields: [
      ['full_name', 'Full name', 'text', true], ['specialization', 'Specialization', 'text', true],
      ['phone', 'Phone number', 'tel', true], ['department_id', 'Department', 'department', true],
      ['working_days', 'Working days', 'text', false], ['consultation_fee', 'Consultation fee ($)', 'number', false]
    ],
    columns: [['full_name', 'Doctor'], ['specialization', 'Specialization'], ['department', 'Department'], ['phone', 'Phone'], ['working_days', 'Working days'], ['consultation_fee', 'Fee']]
  },
  appointments: {
    title: 'Appointments', description: 'Schedule visits and keep track of their status.', resource: 'appointments', add: 'Schedule appointment',
    fields: [
      ['patient_id', 'Patient', 'patient', true], ['doctor_id', 'Doctor', 'doctor', true],
      ['appointment_date', 'Appointment date', 'date', true], ['appointment_time', 'Appointment time', 'time', true],
      ['status', 'Status', 'select', false, ['Pending', 'Confirmed', 'Completed', 'Cancelled']],
      ['reason', 'Reason for visit', 'textarea', false, null, true]
    ],
    columns: [['appointment_date', 'Date'], ['appointment_time', 'Time'], ['patient', 'Patient'], ['doctor', 'Doctor'], ['reason', 'Reason'], ['status', 'Status']]
  },
  departments: {
    title: 'Departments', description: 'Organize hospital services and assigned care teams.', resource: 'departments', add: 'Add department',
    fields: [['name', 'Department name', 'text', true], ['location', 'Location', 'text', false], ['description', 'Description', 'textarea', false, null, true]],
    columns: [['name', 'Department'], ['description', 'Description'], ['location', 'Location']]
  },
  'medical-records': {
    title: 'Medical records', description: 'Securely maintain patient diagnoses, treatments, and notes.', resource: 'medical-records', add: 'Add medical record',
    fields: [
      ['patient_id', 'Patient', 'patient', true], ['doctor_id', 'Attending doctor', 'doctor', true],
      ['record_date', 'Record date', 'date', true], ['diagnosis', 'Diagnosis', 'text', true],
      ['treatment', 'Treatment', 'textarea', false, null, true], ['notes', 'Notes', 'textarea', false, null, true]
    ],
    columns: [['record_date', 'Date'], ['patient', 'Patient'], ['doctor', 'Doctor'], ['diagnosis', 'Diagnosis'], ['treatment', 'Treatment']]
  },
  invoices: {
    title: 'Billing', description: 'Create invoices, add services, and record patient payments.', resource: 'invoices', add: 'Create invoice',
    fields: [
      ['patient_id', 'Patient', 'patient', true], ['invoice_date', 'Invoice date', 'date', true],
      ['due_date', 'Due date', 'date', false], ['description', 'Service description', 'text', true],
      ['quantity', 'Quantity', 'number', true], ['unit_price', 'Unit price ($)', 'number', true],
      ['notes', 'Notes', 'textarea', false, null, true]
    ],
    columns: [['invoice_date', 'Invoice date'], ['patient', 'Patient'], ['total', 'Total'], ['paid', 'Paid'], ['status', 'Status']]
  }
};

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}
function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}
function money(value) { return `$${Number(value || 0).toFixed(2)}`; }
function niceDate(value) {
  if (!value) return '—';
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}
function initials(name) {
  return String(name || '?').split(/\s+/).slice(0, 2).map(part => part[0] || '').join('').toUpperCase();
}
function toast(message, error = false) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.toggle('error', error);
  element.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => element.classList.remove('show'), 3200);
}
async function api(url, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (state.csrf && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method)) headers['X-CSRF-Token'] = state.csrf;
  let response;
  try {
    response = await fetch(url, { credentials: 'same-origin', ...options, headers });
  } catch {
    throw new Error('Could not reach the server. Check that the Flask application is running.');
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
  return result;
}

async function initialize() {
  try {
    const user = await api('/api/auth/me');
    if (user.authenticated) {
      state.csrf = user.csrf_token;
      state.username = user.username;
      showApplication();
    } else {
      showLogin();
    }
  } catch (error) {
    showLogin();
    $('#login-error').textContent = error.message;
  }
}
function showLogin() {
  $('#login-screen').hidden = false;
  $('#application').hidden = true;
}
function showApplication() {
  $('#login-screen').hidden = true;
  $('#application').hidden = false;
  $('#username-label').textContent = state.username;
  loadOptions().then(() => renderPage());
}
async function loadOptions() {
  try { state.options = await api('/api/options'); }
  catch (error) { toast(error.message, true); }
}

$('#login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = $('button[type="submit"]', event.currentTarget);
  button.disabled = true;
  $('#login-error').textContent = '';
  try {
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const result = await api('/api/auth/login', { method: 'POST', body: JSON.stringify(values) });
    state.csrf = result.csrf_token;
    state.username = result.username;
    showApplication();
  } catch (error) {
    $('#login-error').textContent = error.message;
  } finally { button.disabled = false; }
});
$('#logout-button').addEventListener('click', async () => {
  try { await api('/api/auth/logout', { method: 'POST', body: '{}' }); }
  finally {
    state.csrf = '';
    showLogin();
    $('#login-form').reset();
    $('#login-error').textContent = '';
  }
});
$('#menu-button').addEventListener('click', () => $('#sidebar').classList.toggle('open'));
window.addEventListener('hashchange', () => {
  state.page = location.hash.slice(1) || 'dashboard';
  $('#sidebar').classList.remove('open');
  renderPage();
});

function renderPage() {
  state.page = location.hash.slice(1) || 'dashboard';
  if (state.page !== 'dashboard' && !pages[state.page]) state.page = 'dashboard';
  $$('.navigation a').forEach(link => link.classList.toggle('active', link.dataset.page === state.page));
  const title = state.page === 'dashboard' ? 'Dashboard' : pages[state.page].title;
  $('#breadcrumb-current').textContent = title;
  if (state.page === 'dashboard') renderDashboard();
  else renderResourcePage(state.page);
}
async function renderDashboard() {
  $('#page-content').innerHTML = `<div class="page-heading"><div><h1>Good ${new Date().getHours() < 12 ? 'morning' : 'afternoon'}, ${esc(state.username)}</h1><p>Here is what's happening at your hospital today.</p></div><span class="date-label">${esc(new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }))}</span></div><div class="stats-grid" id="dashboard-stats"></div><div class="dashboard-grid"><section class="panel"><div class="panel-heading"><div><h2>Department overview</h2><p>Patient visits by department</p></div><a class="text-link" href="#departments">View departments →</a></div><div id="department-chart" class="chart-list"></div></section><section class="panel"><div class="panel-heading"><div><h2>Upcoming appointments</h2><p>Today and the days ahead</p></div><a class="text-link" href="#appointments">View all →</a></div><div id="upcoming-list" class="appointment-list"></div></section></div><section class="table-card section-spacer"><div class="table-toolbar"><h2>Recently registered patients</h2><a class="text-link" href="#patients">View all patients →</a></div><div class="table-wrap" id="recent-patients"></div></section>`;
  try {
    const data = await api('/api/dashboard');
    $('#dashboard-stats').innerHTML = [
      ['Total patients', data.patients, 'Registered patient profiles', '♙', ''],
      ['Medical staff', data.doctors, 'Active doctors', '✚', 'teal'],
      ["Today's appointments", data.appointments_today, 'Scheduled for today', '▦', 'purple'],
      ['Departments', data.departments, 'Hospital care teams', '▤', 'orange']
    ].map(([label, value, note, icon, color]) => `<article class="stat-card"><div class="stat-top"><span>${label}</span><span class="stat-icon ${color}">${icon}</span></div><div class="stat-value">${value}</div><div class="stat-note">${note}</div></article>`).join('');
    const max = Math.max(1, ...data.department_stats.map(row => row.patients));
    $('#department-chart').innerHTML = data.department_stats.length ? data.department_stats.map(row => `<div class="chart-row"><span title="${esc(row.name)}">${esc(row.name)}</span><div class="chart-track"><div class="chart-bar" style="width:${Math.max(3, row.patients / max * 100)}%"></div></div><strong>${row.patients}</strong></div>`).join('') : '<div class="empty-state">No departments yet.</div>';
    $('#upcoming-list').innerHTML = data.upcoming_appointments.length ? data.upcoming_appointments.map(row => {
      const date = new Date(`${row.appointment_date}T00:00:00`);
      return `<div class="appointment-item"><div class="date-tile"><strong>${date.getDate()}</strong><small>${date.toLocaleDateString(undefined, { month: 'short' })}</small></div><div><strong>${esc(row.patient)}</strong><small>${esc(row.appointment_time)} · ${esc(row.doctor)}</small></div><span class="status ${statusClass(row.status)}">${esc(row.status)}</span></div>`;
    }).join('') : '<div class="empty-state">No upcoming appointments scheduled.</div>';
    $('#recent-patients').innerHTML = data.recent_patients.length ? `<table><thead><tr><th>Patient ID</th><th>Patient</th><th>Registered</th><th></th></tr></thead><tbody>${data.recent_patients.map(patient => `<tr><td class="code">${esc(patient.patient_code)}</td><td><div class="person-cell"><span class="person-avatar">${esc(initials(patient.full_name))}</span><span class="person-name">${esc(patient.full_name)}</span></div></td><td>${niceDate(patient.registration_date)}</td><td><button class="action-button" data-open-detail="patients" data-id="${patient.id}">View</button></td></tr>`).join('')}</tbody></table>` : '<div class="empty-state">No patients registered yet.</div>';
  } catch (error) { toast(error.message, true); }
}
function statusClass(status) { return String(status || '').toLowerCase().replace(/\s+/g, '-'); }

async function renderResourcePage(page) {
  const config = pages[page];
  $('#page-content').innerHTML = `<div class="page-heading"><div><h1>${config.title}</h1><p>${config.description}</p></div><button class="button primary" id="add-record"><span class="plus">+</span>${config.add}</button></div><section class="table-card"><div class="table-toolbar"><h2>${config.title} directory</h2><div class="toolbar-actions"><label class="search-box"><span>⌕</span><input id="table-search" type="search" placeholder="Search ${config.title.toLowerCase()}..." aria-label="Search ${config.title}"></label></div></div><div class="table-wrap" id="resource-table"></div><div class="table-footer"><span id="table-count"></span><span>Changes are saved to the hospital database</span></div></section>`;
  $('#add-record').addEventListener('click', () => openForm(page));
  $('#table-search').addEventListener('input', () => {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => loadTable(page), 220);
  });
  await loadTable(page);
}
async function loadTable(page) {
  try {
    const search = $('#table-search')?.value || '';
    const rows = await api(`/api/${pages[page].resource}?search=${encodeURIComponent(search)}`);
    const config = pages[page];
    if (!rows.length) {
      $('#resource-table').innerHTML = `<div class="empty-state"><strong>${search ? 'No matching records' : `No ${config.title.toLowerCase()} yet`}</strong>${search ? 'Try another search term.' : `Use “${config.add}” to get started.`}</div>`;
      $('#table-count').textContent = '0 records';
      return;
    }
    $('#resource-table').innerHTML = `<table><thead><tr>${config.columns.map(([, label]) => `<th>${label}</th>`).join('')}<th>Actions</th></tr></thead><tbody>${rows.map(row => `<tr>${config.columns.map(([key]) => `<td>${cell(page, row, key)}</td>`).join('')}<td><div class="row-actions">${rowActions(page, row)}</div></td></tr>`).join('')}</tbody></table>`;
    $('#table-count').textContent = `${rows.length} ${rows.length === 1 ? 'record' : 'records'}`;
  } catch (error) { $('#resource-table').innerHTML = `<div class="empty-state"><strong>Couldn't load records</strong>${esc(error.message)}</div>`; }
}
function cell(page, row, key) {
  const value = row[key];
  if (key === 'full_name' || key === 'patient' || key === 'doctor') return `<div class="person-cell"><span class="person-avatar ${key === 'doctor' ? 'teal' : ''}">${esc(initials(value))}</span><span class="person-name">${esc(value || '—')}${key === 'full_name' && page === 'patients' ? `<small class="person-sub">${esc(row.patient_code)}</small>` : ''}</span></div>`;
  if (key === 'patient_code') return `<span class="code">${esc(value)}</span>`;
  if (key === 'status') return `<span class="status ${statusClass(value)}">${esc(value)}</span>`;
  if (key === 'total' || key === 'paid' || key === 'consultation_fee') return money(value);
  if (key.endsWith('_date')) return niceDate(value);
  return esc(value || '—');
}
function rowActions(page, row) {
  const actions = `<button class="action-button" data-open-detail="${page}" data-id="${row.id}">View</button><button class="action-button" data-edit="${page}" data-id="${row.id}">Edit</button>`;
  const payment = page === 'invoices' ? `<button class="action-button" data-add-item="${row.id}">Add service</button>${Number(row.total) > Number(row.paid) ? `<button class="action-button" data-payment="${row.id}">Payment</button>` : ''}` : '';
  const cancel = page === 'appointments' && !['Cancelled', 'Completed'].includes(row.status) ? `<button class="action-button" data-cancel="${row.id}">Cancel</button>` : '';
  return `${actions}${payment}${cancel}<button class="action-button delete" data-delete="${page}" data-id="${row.id}">Delete</button>`;
}

function fieldControl(field, current = {}) {
  const [name, label, type, required, choices, full] = field;
  const value = current[name] ?? (name === 'registration_date' || name === 'invoice_date' || name === 'record_date' ? localDate() : name === 'appointment_date' ? localDate() : name === 'quantity' ? 1 : name === 'status' ? (state.page === 'appointments' ? 'Pending' : 'Unpaid') : name === 'consultation_fee' || name === 'unit_price' ? 0 : '');
  const id = `field-${name}`;
  const klass = full ? 'field-label field-full' : 'field-label';
  const req = required ? 'required' : '';
  let input;
  if (type === 'textarea') input = `<textarea id="${id}" name="${name}" ${req}>${esc(value)}</textarea>`;
  else if (type === 'patient') input = selectControl(name, label, state.options.patients.map(item => [item.id, `${item.patient_code} · ${item.full_name}`]), value, required);
  else if (type === 'doctor') input = selectControl(name, label, state.options.doctors.map(item => [item.id, item.full_name]), value, required);
  else if (type === 'department') input = selectControl(name, label, state.options.departments.map(item => [item.id, item.name]), value, required);
  else if (type === 'select') input = `<select id="${id}" name="${name}" ${req}>${choices.map(option => `<option value="${esc(option)}" ${String(value) === option ? 'selected' : ''}>${option ? esc(option) : 'Select blood group'}</option>`).join('')}</select>`;
  else input = `<input id="${id}" name="${name}" type="${type}" value="${esc(value)}" ${req} ${type === 'number' ? `min="${name === 'age' ? 0 : name === 'quantity' ? 1 : 0}" step="${name === 'consultation_fee' || name === 'unit_price' ? '0.01' : '1'}"` : ''}>`;
  return `<label class="${klass}" for="${id}">${label}${required ? ' *' : ''}${input}</label>`;
}
function selectControl(name, label, options, value, required) {
  return `<select id="field-${name}" name="${name}" ${required ? 'required' : ''}><option value="">Select ${label.toLowerCase()}</option>${options.map(([id, name]) => `<option value="${id}" ${String(value) === String(id) ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select>`;
}
async function openForm(page, id = null) {
  const config = pages[page];
  let record = {};
  if (id) {
    try { record = await api(`/api/${config.resource}/${id}`); }
    catch (error) { toast(error.message, true); return; }
  }
  $('#dialog-eyebrow').textContent = config.title.toUpperCase();
  $('#dialog-title').textContent = id ? `Edit ${singular(page)}` : config.add;
  $('#save-button').textContent = id ? 'Save changes' : 'Save record';
  $('#dialog-error').textContent = '';
  const formFields = page === 'invoices' && id
    ? config.fields.filter(([name]) => !['description', 'quantity', 'unit_price'].includes(name))
    : config.fields;
  $('#form-fields').innerHTML = formFields.map(field => fieldControl(field, record)).join('');
  const dialog = $('#record-dialog');
  dialog.dataset.page = page;
  dialog.dataset.id = id || '';
  dialog.showModal();
}
function singular(page) {
  return ({ patients: 'patient', doctors: 'doctor', appointments: 'appointment', departments: 'department', 'medical-records': 'medical record', invoices: 'invoice' })[page];
}
$('#record-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const dialog = $('#record-dialog');
  const page = dialog.dataset.page;
  const id = dialog.dataset.id;
  const formData = Object.fromEntries(new FormData(form));
  const config = pages[page];
  let payload = {};
  config.fields.forEach(([name, , type]) => {
    if (name === 'description' && page === 'invoices') return;
    if (name === 'quantity' || name === 'unit_price') return;
    if (name === 'notes' && page === 'invoices') payload[name] = formData[name] || '';
    else if (formData[name] !== '') payload[name] = type === 'number' ? Number(formData[name]) : formData[name];
  });
  if (page === 'invoices' && !id) payload.items = [{
    description: formData.description,
    quantity: Number(formData.quantity),
    unit_price: Number(formData.unit_price)
  }];
  const save = $('#save-button');
  save.disabled = true;
  $('#dialog-error').textContent = '';
  try {
    const result = await api(id ? `/api/${config.resource}/${id}` : `/api/${config.resource}`, {
      method: id ? 'PUT' : 'POST', body: JSON.stringify(payload)
    });
    dialog.close();
    toast(id ? 'Changes saved successfully.' : 'Record created successfully.');
    await loadOptions();
    renderPage();
  } catch (error) { $('#dialog-error').textContent = error.message; }
  finally { save.disabled = false; }
});

document.addEventListener('click', async event => {
  const target = event.target.closest('button');
  if (!target) return;
  if (target.matches('[data-close-dialog]')) target.closest('dialog').close();
  if (target.dataset.edit) openForm(target.dataset.edit, target.dataset.id);
  if (target.dataset.openDetail) openDetails(target.dataset.openDetail, target.dataset.id);
  if (target.dataset.delete) deleteRecord(target.dataset.delete, target.dataset.id);
  if (target.dataset.payment) recordPayment(target.dataset.payment);
  if (target.dataset.addItem) addInvoiceService(target.dataset.addItem);
  if (target.dataset.cancel) cancelAppointment(target.dataset.cancel);
});
async function deleteRecord(page, id) {
  const config = pages[page];
  if (!confirm(`Delete this ${singular(page)}? This cannot be undone.`)) return;
  try {
    await api(`/api/${config.resource}/${id}`, { method: 'DELETE' });
    toast('Record deleted.');
    await loadOptions();
    renderPage();
  } catch (error) { toast(error.message, true); }
}
async function cancelAppointment(id) {
  if (!confirm('Cancel this appointment?')) return;
  try {
    await api(`/api/appointments/${id}`, { method: 'PUT', body: JSON.stringify({ status: 'Cancelled' }) });
    toast('Appointment cancelled.');
    renderPage();
  } catch (error) { toast(error.message, true); }
}
async function openDetails(page, id) {
  const config = pages[page];
  try {
    const row = await api(`/api/${config.resource}/${id}`);
    const labels = {
      patient_code: 'Patient ID', full_name: 'Full name', age: 'Age', gender: 'Gender', phone: 'Phone', address: 'Address', blood_group: 'Blood group', registration_date: 'Registration date',
      specialization: 'Specialization', department_id: 'Department ID', department: 'Department', working_days: 'Working days', consultation_fee: 'Consultation fee',
      patient_id: 'Patient ID', doctor_id: 'Doctor ID', appointment_date: 'Appointment date', appointment_time: 'Time', record_date: 'Record date',
      diagnosis: 'Diagnosis', treatment: 'Treatment', notes: 'Notes', name: 'Name', location: 'Location', description: 'Description',
      invoice_date: 'Invoice date', due_date: 'Due date', status: 'Status', total: 'Total', paid: 'Paid'
    };
    $('#detail-title').textContent = row.full_name || row.name || row.patient || `${singular(page)[0].toUpperCase()}${singular(page).slice(1)} details`;
    let pairs = Object.entries(row).filter(([key, value]) => labels[key] && value !== null && value !== '').map(([key, value]) => [labels[key], key.includes('date') ? niceDate(value) : key === 'consultation_fee' || key === 'total' || key === 'paid' ? money(value) : value]);
    if (page === 'doctors') {
      const dep = state.options.departments.find(item => String(item.id) === String(row.department_id));
      pairs = pairs.map(pair => pair[0] === 'Department ID' ? ['Department', dep?.name || pair[1]] : pair);
    }
    if (page === 'appointments' || page === 'medical-records') {
      const [patient, doctor] = await Promise.all([
        api(`/api/patients/${row.patient_id}`), api(`/api/doctors/${row.doctor_id}`)
      ]);
      pairs = pairs.map(pair => pair[0] === 'Patient ID' ? ['Patient', patient.full_name] : pair[0] === 'Doctor ID' ? ['Doctor', doctor.full_name] : pair);
    }
    if (page === 'departments') {
      const doctors = await api('/api/doctors');
      const assigned = doctors.filter(doctor => String(doctor.department_id) === String(row.id));
      pairs.push(['Assigned doctors', assigned.map(doctor => doctor.full_name).join(', ') || 'No doctors assigned']);
    }
    $('#detail-content').innerHTML = `<div class="detail-list">${pairs.map(([label, value]) => `<div class="detail-item"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`).join('')}</div>${page === 'invoices' ? invoiceDetails(row) : ''}`;
    if (page === 'invoices') {
      const payments = await api(`/api/invoices/${id}/payments`);
      $('#detail-content').insertAdjacentHTML('beforeend', `<h3 class="detail-section-title">Payment history</h3>${payments.length ? `<div class="detail-list">${payments.map(payment => `<div class="detail-item"><small>${niceDate(payment.payment_date)} · ${esc(payment.method)}</small><strong>${money(payment.amount)}</strong></div>`).join('')}</div>` : '<p class="muted">No payments recorded.</p>'}`);
    }
    $('#detail-dialog').showModal();
  } catch (error) { toast(error.message, true); }
}
function invoiceDetails(invoice) {
  const items = invoice.items || [];
  return `<h3 class="detail-section-title">Invoice services</h3>${items.length ? `<div class="table-wrap"><table><thead><tr><th>Service</th><th>Qty</th><th>Unit price</th><th>Amount</th></tr></thead><tbody>${items.map(item => `<tr><td>${esc(item.description)}</td><td>${item.quantity}</td><td>${money(item.unit_price)}</td><td>${money(item.quantity * item.unit_price)}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">No services added.</p>'}`;
}
async function recordPayment(id) {
  const amountText = prompt('Enter payment amount ($):');
  if (amountText === null) return;
  const amount = Number(amountText);
  if (!Number.isFinite(amount) || amount <= 0) { toast('Enter a valid payment amount.', true); return; }
  const method = prompt('Payment method: Cash, Card, Insurance, or Bank transfer', 'Cash');
  if (method === null) return;
  try {
    await api(`/api/invoices/${id}/payments`, { method: 'POST', body: JSON.stringify({ amount, method }) });
    toast('Payment recorded successfully.');
    renderPage();
  } catch (error) { toast(error.message, true); }
}
async function addInvoiceService(id) {
  const description = prompt('Service description:');
  if (description === null) return;
  const quantityText = prompt('Quantity:', '1');
  if (quantityText === null) return;
  const priceText = prompt('Unit price ($):');
  if (priceText === null) return;
  const quantity = Number(quantityText);
  const unit_price = Number(priceText);
  if (!description.trim() || !Number.isInteger(quantity) || quantity < 1 || !Number.isFinite(unit_price) || unit_price < 0) {
    toast('Enter a service description, positive whole quantity, and valid price.', true);
    return;
  }
  try {
    await api(`/api/invoices/${id}/items`, {
      method: 'POST', body: JSON.stringify({ description, quantity, unit_price })
    });
    toast('Service added to invoice.');
    renderPage();
  } catch (error) { toast(error.message, true); }
}

initialize();
