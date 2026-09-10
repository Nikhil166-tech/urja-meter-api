// Urja Meter Ops Clean API Dashboard Client
let map = null;
let mapMarkers = [];
let telemetryChartInstance = null;
let analyticsCharts = {};

let currentPage = 1;
const pageSize = 20;

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initMap();
  loadKpiSummary();
  loadMetersTable();
  loadTransformersTable();
  loadHierarchyTree();
  loadAnalytics();

  // Event Listeners
  document.getElementById('btnForceSync').addEventListener('click', forceSync);
  document.getElementById('meterSearchInput').addEventListener('input', debounce(loadMetersTable, 300));
  document.getElementById('filterStatus').addEventListener('change', () => { currentPage = 1; loadMetersTable(); });
  document.getElementById('filterMake').addEventListener('change', () => { currentPage = 1; loadMetersTable(); });
  document.getElementById('filterPhase').addEventListener('change', () => { currentPage = 1; loadMetersTable(); });
  document.getElementById('filterInstallType').addEventListener('change', () => { currentPage = 1; loadMetersTable(); });
  document.getElementById('btnResetFilters').addEventListener('click', resetFilters);

  document.getElementById('btnPrevPage').addEventListener('click', () => { if (currentPage > 1) { currentPage--; loadMetersTable(); }});
  document.getElementById('btnNextPage').addEventListener('click', () => { currentPage++; loadMetersTable(); });

  document.getElementById('btnSearchNearby').addEventListener('click', searchNearby);
  document.getElementById('btnModalClose').addEventListener('click', closeModal);
  document.getElementById('meterModal').addEventListener('click', (e) => {
    if (e.target.id === 'meterModal') closeModal();
  });

  initModalTabs();
});

function initTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      document.getElementById(targetId).classList.add('active');

      if (targetId === 'tabMap' && map) {
        setTimeout(() => map.invalidateSize(), 200);
      }
    });
  });
}

function initModalTabs() {
  const tabs = document.querySelectorAll('.modal-tab-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.modal-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.getAttribute('data-modaltab')).classList.add('active');
    });
  });
}

function initMap() {
  map = L.map('map').setView([26.9124, 75.7873], 12);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; CartoDB &copy; OpenStreetMap',
    maxZoom: 19
  }).addTo(map);

  map.on('click', (e) => {
    document.getElementById('geoLatInput').value = e.latlng.lat.toFixed(4);
    document.getElementById('geoLngInput').value = e.latlng.lng.toFixed(4);
    searchNearby();
  });

  loadAllMapMarkers();
}

async function loadAllMapMarkers() {
  try {
    const res = await fetch('/api/meters?page=1&page_size=500');
    const data = await res.json();
    mapMarkers.forEach(m => map.removeLayer(m));
    mapMarkers = [];

    const bounds = [];
    data.meters.forEach(m => {
      if (!m.location) return;
      const color = m.install_status === 'Installed' ? '#34d399' : (m.install_status === 'Faulty' ? '#f87171' : '#94a3b8');
      const marker = L.circleMarker([m.location.latitude, m.location.longitude], {
        radius: 5,
        fillColor: color,
        color: '#000',
        weight: 1,
        opacity: 0.8,
        fillOpacity: 0.9
      }).addTo(map);

      marker.bindPopup(`
        <div style="color: #111;">
          <strong>Meter ${m.meter_id}</strong><br/>
          Make: ${m.make} (${m.phase_type})<br/>
          Status: <span style="font-weight:bold; color:${color}">${m.install_status}</span><br/>
          DT: ${m.dt_code}<br/>
          <button onclick="openMeterModal('${m.meter_id}')" style="margin-top:5px; padding:3px 8px; cursor:pointer;">View Details & Telemetry</button>
        </div>
      `);
      mapMarkers.push(marker);
      bounds.push([m.location.latitude, m.location.longitude]);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [20, 20] });
    }
  } catch (err) {
    console.error('Error loading map markers:', err);
  }
}

async function loadKpiSummary() {
  try {
    const res = await fetch('/api/analytics/summary');
    const data = await res.json();
    
    document.getElementById('kpiTotalMeters').innerText = data.total_meters.toLocaleString();
    const installed = data.status_distribution['Installed'] || 0;
    const faulty = data.status_distribution['Faulty'] || 0;
    
    document.getElementById('kpiInstalled').innerText = installed.toLocaleString();
    document.getElementById('kpiFaulty').innerText = faulty.toLocaleString();
    document.getElementById('kpiTransformers').innerText = data.total_transformers;
    
    const pct = ((installed / data.total_meters) * 100).toFixed(1);
    document.getElementById('kpiInstalledPct').innerText = `${pct}% of total fleet`;
    document.getElementById('kpiTotalCapacity').innerText = `${data.total_transformer_capacity_kva.toLocaleString()} kVA Capacity`;
    document.getElementById('kpiMetersMeta').innerText = `Across ${Object.keys(data.zone_meter_counts).length} Distribution Zones`;
  } catch (err) {
    console.error('KPI error:', err);
  }
}

async function loadMetersTable() {
  const q = document.getElementById('meterSearchInput').value;
  const status = document.getElementById('filterStatus').value;
  const make = document.getElementById('filterMake').value;
  const phase = document.getElementById('filterPhase').value;
  const installType = document.getElementById('filterInstallType').value;

  const params = new URLSearchParams({
    page: currentPage,
    page_size: pageSize
  });
  if (q) params.append('q', q);
  if (status) params.append('status', status);
  if (make) params.append('make', make);
  if (phase) params.append('phase', phase);
  if (installType) params.append('install_type', installType);

  try {
    const res = await fetch(`/api/meters?${params.toString()}`);
    const data = await res.json();
    
    const tbody = document.getElementById('metersTableBody');
    tbody.innerHTML = '';

    if (data.meters.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-muted">No meters found matching filters.</td></tr>';
      return;
    }

    data.meters.forEach(m => {
      const tr = document.createElement('tr');
      const badgeClass = m.install_status === 'Installed' ? 'badge-installed' : (m.install_status === 'Faulty' ? 'badge-faulty' : 'badge-decom');
      tr.innerHTML = `
        <td><strong><a href="javascript:void(0)" onclick="openMeterModal('${m.meter_id}')" class="text-primary">${m.meter_id}</a></strong></td>
        <td>${m.serial_no}</td>
        <td>${m.make}</td>
        <td>${m.phase_type}</td>
        <td>${m.install_type}</td>
        <td><span class="badge ${badgeClass}">${m.install_status}</span></td>
        <td>${m.dt_code}</td>
        <td>${m.feeder_code || '—'}</td>
        <td><button class="btn btn-outline btn-sm" onclick="openMeterModal('${m.meter_id}')">Telemetry</button></td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById('paginationInfo').innerText = `Showing ${(data.page - 1) * data.page_size + 1}–${Math.min(data.page * data.page_size, data.total)} of ${data.total} meters`;
    document.getElementById('currentPageDisplay').innerText = `Page ${data.page} of ${data.total_pages}`;
    document.getElementById('btnPrevPage').disabled = data.page <= 1;
    document.getElementById('btnNextPage').disabled = data.page >= data.total_pages;
  } catch (err) {
    console.error('Error loading meters table:', err);
  }
}

async function loadTransformersTable() {
  try {
    const res = await fetch('/api/transformers');
    const data = await res.json();
    const tbody = document.getElementById('transformersTableBody');
    tbody.innerHTML = '';

    data.forEach(t => {
      const tr = document.createElement('tr');
      const estLoad = (t.connected_meters_count * 3.5).toFixed(1);
      const utilPct = ((estLoad / (t.capacity_kva * 0.9)) * 100).toFixed(0);
      tr.innerHTML = `
        <td><strong>${t.code}</strong></td>
        <td>${t.name}</td>
        <td>${t.feeder_code}</td>
        <td>${t.capacity_kva} kVA</td>
        <td><span class="badge badge-installed">${t.connected_meters_count} meters</span></td>
        <td>~${estLoad} kW</td>
        <td><span class="text-accent font-semibold">${utilPct}%</span></td>
        <td><button class="btn btn-outline btn-sm" onclick="filterByDt('${t.code}')">View Meters</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading transformers:', err);
  }
}

function filterByDt(dtCode) {
  document.querySelector('[data-tab="tabMeters"]').click();
  document.getElementById('meterSearchInput').value = dtCode;
  currentPage = 1;
  loadMetersTable();
}

async function loadHierarchyTree() {
  try {
    const res = await fetch('/api/hierarchy');
    const data = await res.json();
    const container = document.getElementById('hierarchyTreeContainer');
    container.innerHTML = '';

    data.tree.forEach(zone => {
      container.appendChild(renderTreeNode(zone));
    });
  } catch (err) {
    console.error('Error loading hierarchy:', err);
  }
}

function renderTreeNode(node) {
  const el = document.createElement('div');
  el.className = 'tree-node';

  const header = document.createElement('div');
  header.className = 'tree-node-header';
  header.innerHTML = `
    <span class="tree-tier-badge">${node.level}</span>
    <strong>${node.id}</strong> — ${node.name}
    <span class="text-muted text-xs">(${node.meter_count} meters)</span>
  `;

  const childContainer = document.createElement('div');
  childContainer.className = 'tree-children';

  if (node.children && node.children.length > 0) {
    node.children.forEach(child => {
      childContainer.appendChild(renderTreeNode(child));
    });
  }

  el.appendChild(header);
  el.appendChild(childContainer);
  return el;
}

async function searchNearby() {
  const lat = parseFloat(document.getElementById('geoLatInput').value);
  const lng = parseFloat(document.getElementById('geoLngInput').value);
  const radius = parseFloat(document.getElementById('geoRadiusInput').value);

  const container = document.getElementById('nearbyListContainer');
  container.innerHTML = '<div class="text-muted text-sm py-2">Searching...</div>';

  try {
    const res = await fetch(`/api/meters/nearby?lat=${lat}&lng=${lng}&radius_km=${radius}&limit=50`);
    const data = await res.json();
    document.getElementById('nearbyCount').innerText = data.length;
    container.innerHTML = '';

    if (data.length === 0) {
      container.innerHTML = '<div class="empty-state">No meters within search radius.</div>';
      return;
    }

    data.forEach(m => {
      const item = document.createElement('div');
      item.className = 'nearby-item';
      item.onclick = () => openMeterModal(m.meter_id);
      item.innerHTML = `
        <div>
          <strong>${m.meter_id}</strong> (${m.make})<br/>
          <span class="text-muted text-xs">DT: ${m.dt_code}</span>
        </div>
        <div class="text-right">
          <span class="text-primary font-semibold">${m.distance_km} km</span>
        </div>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    console.error('Nearby error:', err);
  }
}

async function openMeterModal(meterId) {
  const modal = document.getElementById('meterModal');
  document.getElementById('modalMeterTitle').innerText = `Meter ${meterId}`;
  modal.classList.add('active');

  // Load specs
  try {
    const res = await fetch(`/api/meters/${meterId}`);
    const detail = await res.json();

    const badge = document.getElementById('modalMeterBadge');
    badge.innerText = detail.install_status;
    badge.className = 'badge ' + (detail.install_status === 'Installed' ? 'badge-installed' : (detail.install_status === 'Faulty' ? 'badge-faulty' : 'badge-decom'));

    // Specs Grid
    const specsContainer = document.getElementById('specsGrid');
    specsContainer.innerHTML = '';
    detail.nameplate.forEach(p => {
      const item = document.createElement('div');
      item.className = 'spec-item';
      item.innerHTML = `<div class="spec-name">${p.name}</div><div class="spec-val">${p.value}</div>`;
      specsContainer.appendChild(item);
    });

    // Hierarchy path
    const pathContainer = document.getElementById('modalHierarchyPath');
    pathContainer.innerHTML = '';
    if (detail.hierarchy) {
      const tiers = ['zone', 'circle', 'division', 'subdivision', 'substation', 'feeder', 'dt'];
      tiers.forEach((t, i) => {
        const node = detail.hierarchy[t];
        if (node) {
          const bNode = document.createElement('div');
          bNode.className = 'breadcrumb-node';
          bNode.innerHTML = `<span class="tree-tier-badge">${t}</span> <strong>${node.code}</strong> ${node.name}`;
          pathContainer.appendChild(bNode);
          if (i < tiers.length - 1) {
            const arrow = document.createElement('span');
            arrow.innerHTML = '➔';
            arrow.className = 'text-muted';
            pathContainer.appendChild(arrow);
          }
        }
      });
    }
  } catch (err) {
    console.error('Specs error:', err);
  }

  // Load telemetry
  try {
    const res = await fetch(`/api/meters/${meterId}/energy`);
    const energy = await res.json();

    document.getElementById('telemetryNetKwh').innerText = energy.net_consumption_kwh !== null ? `${energy.net_consumption_kwh} kWh` : '—';
    document.getElementById('telemetryAvgVoltage').innerText = energy.avg_voltage !== null ? `${energy.avg_voltage} V` : '—';
    document.getElementById('telemetryAvgPf').innerText = energy.avg_power_factor !== null ? energy.avg_power_factor : '—';
    document.getElementById('telemetryAnomaliesCount').innerText = energy.anomalies.length;

    // Anomalies
    const anomContainer = document.getElementById('anomaliesList');
    anomContainer.innerHTML = '';
    if (energy.anomalies.length === 0) {
      anomContainer.innerHTML = '<div class="text-success text-sm py-2">✓ No voltage sags, swells, or spikes detected in telemetry window.</div>';
    } else {
      energy.anomalies.forEach(a => {
        const div = document.createElement('div');
        div.className = 'spec-item mb-2';
        div.innerHTML = `
          <div class="flex-between">
            <strong class="text-danger">${a.type.toUpperCase()}</strong>
            <span class="text-muted text-xs">${a.timestamp}</span>
          </div>
          <div class="text-sm">${a.description}</div>
        `;
        anomContainer.appendChild(div);
      });
    }

    // Readings table
    const tableBody = document.getElementById('readingsTableBody');
    tableBody.innerHTML = '';
    energy.readings.slice(-50).reverse().forEach(r => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${r.timestamp}</td>
        <td>${r.kwh !== null ? r.kwh : '—'}</td>
        <td>${r.kvah !== null ? r.kvah : '—'}</td>
        <td>${r.voltage_r !== null ? r.voltage_r + ' V' : '—'}</td>
        <td>${r.power_factor !== null ? r.power_factor : '—'}</td>
      `;
      tableBody.appendChild(row);
    });

    // Chart.js
    renderTelemetryChart(energy.readings.slice(-48));
  } catch (err) {
    console.error('Telemetry error:', err);
  }
}

function renderTelemetryChart(readings) {
  const ctx = document.getElementById('telemetryChart').getContext('2d');
  if (telemetryChartInstance) {
    telemetryChartInstance.destroy();
  }

  const labels = readings.map(r => r.timestamp.split(' ')[1] || r.timestamp);
  const voltages = readings.map(r => r.voltage_r);
  const kwhs = readings.map(r => r.kwh);

  telemetryChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Voltage R-Phase (V)',
          data: voltages,
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56, 189, 248, 0.1)',
          yAxisID: 'yVoltage',
          tension: 0.3,
          fill: true
        }
      ]
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { grid: { color: '#202d4a' }, ticks: { color: '#94a3b8' } },
        yVoltage: {
          type: 'linear',
          position: 'left',
          grid: { color: '#202d4a' },
          ticks: { color: '#38bdf8' },
          suggestedMin: 200,
          suggestedMax: 260
        }
      },
      plugins: {
        legend: { labels: { color: '#e2e8f0' } }
      }
    }
  });
}

function closeModal() {
  document.getElementById('meterModal').classList.remove('active');
}

async function loadAnalytics() {
  try {
    const res = await fetch('/api/analytics/summary');
    const data = await res.json();

    renderDoughnut('statusChart', Object.keys(data.status_distribution), Object.values(data.status_distribution), ['#34d399', '#f87171', '#94a3b8']);
    renderDoughnut('makeChart', Object.keys(data.make_distribution), Object.values(data.make_distribution), ['#38bdf8', '#818cf8', '#fbbf24', '#f472b6', '#34d399']);
    renderDoughnut('phaseChart', Object.keys(data.phase_distribution), Object.values(data.phase_distribution), ['#0284c7', '#6366f1']);
    renderDoughnut('installTypeChart', Object.keys(data.install_type_distribution), Object.values(data.install_type_distribution), ['#38bdf8', '#fbbf24']);
  } catch (err) {
    console.error('Analytics error:', err);
  }
}

function renderDoughnut(canvasId, labels, data, colors) {
  const ctx = document.getElementById(canvasId).getContext('2d');
  if (analyticsCharts[canvasId]) {
    analyticsCharts[canvasId].destroy();
  }
  analyticsCharts[canvasId] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors,
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#e2e8f0', boxWidth: 12 } }
      }
    }
  });
}

async function forceSync() {
  const btn = document.getElementById('btnForceSync');
  btn.disabled = true;
  btn.innerText = 'Syncing...';
  try {
    await fetch('/api/sync', { method: 'POST' });
    await Promise.all([loadKpiSummary(), loadMetersTable(), loadTransformersTable(), loadAllMapMarkers()]);
  } finally {
    btn.disabled = false;
    btn.innerText = '🔄 Refresh';
  }
}

function resetFilters() {
  document.getElementById('meterSearchInput').value = '';
  document.getElementById('filterStatus').value = '';
  document.getElementById('filterMake').value = '';
  document.getElementById('filterPhase').value = '';
  document.getElementById('filterInstallType').value = '';
  currentPage = 1;
  loadMetersTable();
}

function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}
