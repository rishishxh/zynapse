/* main.js v4 - ZYNAPSE */

var API_URL  = "/api/products";
var PRED_API = "/api/predictions";
var IMG_PATH = "/api/images/";
var FALLBACK = "/static/assets/placeholder_product.png";

var allProducts  = [];
var currentIndex = 0;
var BATCH_SIZE   = 24;

function getEl(id) { return document.getElementById(id); }

var marketplaceContainer = null;
var heroContainer        = null;
var predChartEl          = null;

/* LOAD PRODUCTS */
function loadProducts() {
  marketplaceContainer = getEl("marketplace-container");
  if (!marketplaceContainer) return;

  fetch(API_URL + "?limit=100")
    .then(function(r) { return r.json(); })
    .then(function(json) {
      allProducts  = json.data || [];
      currentIndex = 0;
      marketplaceContainer.innerHTML = "";
      renderBatch();
    })
    .catch(function(e) { console.error("loadProducts error", e); });
}

/* RENDER BATCH */
function renderBatch() {
  marketplaceContainer = getEl("marketplace-container");
  if (!marketplaceContainer) return;

  var batch = allProducts.slice(currentIndex, currentIndex + BATCH_SIZE);

  for (var i = 0; i < batch.length; i++) {
    var p    = batch[i];
    var asin = String(p.asin);
    var img  = IMG_PATH + asin";

    var card = document.createElement("div");
    card.className = "card-dark";

    var html = "";
    html += '<a href="/product.html?asin=' + encodeURIComponent(asin) + '"';
    html += ' style="text-decoration:none;color:inherit;display:block;height:100%;">';
    html += '<div class="card-dark-img-wrapper">';
    html += '<img src="' + img + '" loading="lazy"';
    html += ' onerror="this.onerror=null;this.src=\'' + FALLBACK + '\'">';
    html += '</div>';
    html += '<div class="card-dark-title">' + (p.title || "No Title") + '</div>';
    html += '<div class="card-dark-subtitle">' + (p.categoryName || "Product") + '</div>';
    html += '<div class="card-dark-inline">';
    html += '<div class="card-dark-price">' + Math.floor(p.price || 0) + '</div>';
    html += '<div class="card-dark-stars">&#9733;&#9733;&#9733;&#9733;&#9734;</div>';
    html += '</div>';
    html += '</a>';
    html += '<button class="oracle-btn-purchase"';
    html += ' onclick="event.stopPropagation();event.preventDefault();">Add to Cart</button>';

    card.innerHTML = html;
    marketplaceContainer.appendChild(card);
  }

  currentIndex += BATCH_SIZE;

  var btn = getEl("load-more-btn");
  if (btn) {
    btn.style.display = (currentIndex >= allProducts.length) ? "none" : "block";
  }
}

/* HERO */
function loadHeroProduct() {
  heroContainer = getEl("hero-dynamic-mount");
  if (!heroContainer) return;

  fetch(API_URL + "?limit=1")
    .then(function(r) { return r.json(); })
    .then(function(json) {
      var p = json.data && json.data[0];
      if (!p) return;
      var img = IMG_PATH + String(p.asin)";
      var html = "";
      html += '<div class="hero-dynamic-card">';
      html += '<div class="hero-dynamic-header">';
      html += '<span>Trending</span>';
      html += '<span class="hero-dynamic-surge">+32%</span>';
      html += '</div>';
      html += '<div class="hero-dynamic-img-container">';
      html += '<img src="' + img + '" onerror="this.src=\'' + FALLBACK + '\'">';
      html += '</div>';
      html += '<div class="hero-dynamic-footer"><div>';
      html += '<div class="hero-dynamic-title">' + (p.title || "") + '</div>';
      html += '<div class="hero-dynamic-price">' + Math.floor(p.price || 0) + '</div>';
      html += '</div><button class="hero-cart-btn">&#128722;</button></div>';
      html += '</div>';
      heroContainer.innerHTML = html;
    })
    .catch(function(e) { console.error("loadHeroProduct error", e); });
}

/* PREDICTIONS */
function loadPredictions() {
  predChartEl = getEl("distChart");
  if (!predChartEl) return;

  fetch(PRED_API)
    .then(function(r) { return r.json(); })
    .then(function(response) {
      var rows    = response.data    || [];
      var summary = response.summary || {};
      if (!rows.length) return;

      var avgScore = 0;
      for (var i = 0; i < rows.length; i++) avgScore += (rows[i].demand_score || 0);
      avgScore = (avgScore / rows.length).toFixed(2);

      function set(id, val) { var el = getEl(id); if (el) el.innerText = val || 0; }
      set("stat-surging",      summary.High);
      set("stat-rising",       summary.Medium);
      set("stat-total-bought", response.count);
      set("stat-avg-score",    avgScore);

      var tbody = getEl("pred-tbody");
      if (tbody) {
        var rows_html = "";
        for (var j = 0; j < Math.min(rows.length, 50); j++) {
          var r = rows[j];
          rows_html += "<tr><td>" + (j+1) + "</td><td>" + r.title + "</td><td>" +
            r.demand_level + "</td><td>" + r.demand_score + "</td><td>" +
            r.confidence + "%</td></tr>";
        }
        tbody.innerHTML = rows_html;
      }

      if (window.Chart) {
        if (window.predChart) window.predChart.destroy();
        window.predChart = new Chart(predChartEl, {
          type: "doughnut",
          data: {
            labels: ["High","Medium","Low"],
            datasets: [{ data: [summary.High||0, summary.Medium||0, summary.Low||0],
                         backgroundColor: ["#16a34a","#2563eb","#9ca3af"] }]
          },
          options: { maintainAspectRatio: true, plugins: { legend: { position:"bottom" } } }
        });
      }

      var pl = getEl("pred-loading"); if (pl) pl.style.display = "none";
      var pw = getEl("pred-wrap");    if (pw) pw.style.display = "block";
    })
    .catch(function(e) { console.error("loadPredictions error", e); });
}

/* INIT */
document.addEventListener("DOMContentLoaded", function() {
  marketplaceContainer = getEl("marketplace-container");
  heroContainer        = getEl("hero-dynamic-mount");
  predChartEl          = getEl("distChart");

  if (marketplaceContainer) {
    loadProducts();
    loadHeroProduct();
    var btn = getEl("load-more-btn");
    if (btn) btn.addEventListener("click", renderBatch);
  }

  if (predChartEl) {
    loadPredictions();
  }
});
