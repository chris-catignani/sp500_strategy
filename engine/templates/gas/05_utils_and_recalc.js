
// ==========================================
// Utility & Custom Spreadsheet Functions
// ==========================================
function recalculateSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Executive Summary');
  if (!sheet) {
    SpreadsheetApp.getUi().alert('Executive Summary sheet not found.');
    return;
  }
  var univVal = sheet.getRange('B2').getValue();
  var stratVal = sheet.getRange('D2').getValue();
  var weightVal = sheet.getRange('F2').getValue();
  var horizVal = sheet.getRange('H2').getValue();
  var taxRateVal = sheet.getRange('F3').getValue();
  var taxRateStr = (typeof taxRateVal === 'number') ? (taxRateVal * 100).toFixed(1) + '%' : String(taxRateVal);
  var seedVal = sheet.getRange('H3').getValue();
  var seedStr = (typeof seedVal === 'number') ? '$' + seedVal.toLocaleString() : String(seedVal);
  SpreadsheetApp.flush();
  ss.toast('Spotlight: ' + univVal + ' ' + stratVal + ' (' + weightVal + ', ' + horizVal + '), Tax: ' + taxRateStr + ', Seed: ' + seedStr, 'Recalculation Complete', 4);
}

/**
 * Custom spreadsheet formula to look up exact empirical backtest results or compute
 * piecewise-interpolated performance metrics across tax rates using generated SCENARIO_DATA.
 *
 * For standard simulated tax tiers (0.0%, 15.0%, 20.0%, 30.0%, 37.0%), this function returns
 * the exact empirical engine backtest result.
 * For non-standard intermediate rates (e.g. 24.5%), it computes a piecewise linear interpolation
 * between the two adjacent bounding empirical tiers.
 *
 * @param {number|string} taxRate Tax rate as decimal (e.g. 0.30), percentage string ("30%"), or integer percentage (25). Required.
 * @param {string|number} [optStrategy="Top 5"] Strategy selection ("Top 3", "Top 5", "Top 10", or 3, 5, 10).
 * @param {string|number} [optHorizon="30y"] Horizon ("10y", "20y", "30y", or 10, 20, 30).
 * @param {string} [optWeighting="Market Cap"] Weighting ("Market Cap", "Equal Weight").
 * @param {string} [optUniverse="S&P 500"] Universe ("S&P 500", "All World").
 * @param {string} [optFrequency="Annual"] Rebalance frequency ("Annual", "Quarterly").
 * @param {string} [optMetric="PostLiqCAGR"] Metric to return ("PostLiqCAGR", "AfterTaxCAGR", "PreTaxCAGR", "MaxDD", "TaxDrag", "Alpha", "CumReturn").
 * @return {number|string} Exact or interpolated metric value, or error message string.
 * @customfunction
 */
function RECALCULATE_STRATEGY(taxRate, optStrategy, optHorizon, optWeighting, optUniverse, optFrequency, optMetric) {
  if (taxRate === undefined || taxRate === null || taxRate === '') {
    return 'Tax rate required';
  }

  // Parse tax rate safely (preventing zero-falsiness bug)
  var rate;
  if (typeof taxRate === 'number') {
    if (isNaN(taxRate)) {
      return 'Invalid tax rate';
    }
    if (taxRate > 1.0 && taxRate <= 100.0) {
      rate = taxRate / 100.0;
    } else {
      rate = taxRate;
    }
  } else if (typeof taxRate === 'string') {
    var cleanStr = taxRate.trim();
    var hasPercent = cleanStr.indexOf('%') !== -1;
    var parsed = parseFloat(cleanStr.replace('%', ''));
    if (isNaN(parsed)) {
      return 'Invalid tax rate';
    }
    if (hasPercent || parsed > 1.0) {
      rate = parsed / 100.0;
    } else {
      rate = parsed;
    }
  } else {
    return 'Invalid tax rate';
  }

  // Bounds check: 0.0% to 37.0% simulated bounds
  if (rate < -1e-7 || rate > 0.370001) {
    return 'Tax rate out of simulated bounds (0.0% - 37.0%)';
  }
  if (rate < 0) {
    rate = 0.0;
  }

  // Default dimension options
  var strat = (optStrategy !== undefined && optStrategy !== null && optStrategy !== '') ? String(optStrategy).trim() : 'Top 5';
  var horiz = (optHorizon !== undefined && optHorizon !== null && optHorizon !== '') ? String(optHorizon).trim() : '30y';
  var weight = (optWeighting !== undefined && optWeighting !== null && optWeighting !== '') ? String(optWeighting).trim() : 'Market Cap';
  var univ = (optUniverse !== undefined && optUniverse !== null && optUniverse !== '') ? String(optUniverse).trim() : 'S&P 500';
  var freq = (optFrequency !== undefined && optFrequency !== null && optFrequency !== '') ? String(optFrequency).trim() : 'Annual';
  var metric = (optMetric !== undefined && optMetric !== null && optMetric !== '') ? String(optMetric).trim() : 'PostLiqCAGR';

  // Normalize Universe
  var uLower = univ.toLowerCase().replace(/[\s_-]/g, '');
  if (uLower === 'sp500' || uLower === 'sp' || uLower === 's&p500' || uLower === 'sandp500' || uLower === 'spx' || uLower === 'gspc') {
    univ = 'S&P 500';
  } else if (uLower === 'world' || uLower === 'allworld' || uLower === 'all-world' || uLower === 'msciworld') {
    univ = 'All World';
  }

  // Normalize Strategy & Benchmarks
  var sLower = strat.toLowerCase().replace(/[\s_-]/g, '');
  if (sLower === '3' || sLower === 'top3') {
    strat = 'Top 3';
  } else if (sLower === '5' || sLower === 'top5') {
    strat = 'Top 5';
  } else if (sLower === '10' || sLower === 'top10') {
    strat = 'Top 10';
  } else if (sLower === 'sp500' || sLower === 'sp' || sLower === 's&p500' || sLower === 'sandp500' || sLower === 'spx' || sLower === 'gspc') {
    strat = 'S&P 500';
  } else if (sLower === 'msciworld' || sLower === 'msci') {
    strat = 'MSCI World';
  } else if (sLower === 'fbgrx') {
    strat = 'FBGRX';
  } else if (sLower === 'nasdaq100' || sLower === 'nasdaq' || sLower === 'qqq' || sLower === 'ndx') {
    strat = 'Nasdaq 100';
  } else if (sLower === 'benchmark' || sLower === 'index') {
    strat = (univ === 'All World') ? 'MSCI World' : 'S&P 500';
  }

  // Normalize Horizon
  var hLower = horiz.toLowerCase().trim();
  if (hLower === '10' || hLower === '10y' || hLower === '10yr' || hLower === '10years') {
    horiz = '10y';
  } else if (hLower === '20' || hLower === '20y' || hLower === '20yr' || hLower === '20years') {
    horiz = '20y';
  } else if (hLower === '30' || hLower === '30y' || hLower === '30yr' || hLower === '30years') {
    horiz = '30y';
  }

  // Normalize Weighting
  var wLower = weight.toLowerCase().replace(/[\s_-]/g, '');
  if (wLower === 'marketcap' || wLower === 'cap' || wLower === 'mc') {
    weight = 'Market Cap';
  } else if (wLower === 'equal' || wLower === 'equalweight' || wLower === 'ew') {
    weight = 'Equal Weight';
  }

  // Normalize Frequency
  var fLower = freq.toLowerCase().trim();
  if (fLower === 'annual' || fLower === 'annually' || fLower === 'yearly') {
    freq = 'Annual';
  } else if (fLower === 'quarterly' || fLower === 'quarter') {
    freq = 'Quarterly';
  }

  // Metric column index mapping in SCENARIO_DATA
  var mLower = metric.toLowerCase().replace(/[\s_-]/g, '');
  var colIdx = -1;
  if (mLower === 'postliqcagr' || mLower === 'postliq' || mLower === 'postliquidationcagr') {
    colIdx = 9;
  } else if (mLower === 'aftertaxcagr' || mLower === 'aftertax' || mLower === 'postcagr') {
    colIdx = 8;
  } else if (mLower === 'pretaxcagr' || mLower === 'pretax' || mLower === 'precagr') {
    colIdx = 7;
  } else if (mLower === 'cumreturn' || mLower === 'cumulativereturn') {
    colIdx = 10;
  } else if (mLower === 'finalequity' || mLower === 'wealth') {
    colIdx = 11;
  } else if (mLower === 'totaldividends' || mLower === 'dividends') {
    colIdx = 12;
  } else if (mLower === 'maxdd' || mLower === 'maxdrawdown' || mLower === 'drawdown') {
    colIdx = 13;
  } else if (mLower === 'totaltaxes' || mLower === 'taxes') {
    colIdx = 14;
  } else if (mLower === 'taxdrag' || mLower === 'drag') {
    colIdx = 15;
  } else if (mLower === 'alpha') {
    colIdx = 16;
  } else {
    return 'Invalid metric: ' + metric;
  }

  if (typeof SCENARIO_DATA === 'undefined' || !SCENARIO_DATA || SCENARIO_DATA.length === 0) {
    return 'Scenario data not loaded';
  }

  // Filter matching scenario rows
  var matchedRows = [];
  for (var i = 0; i < SCENARIO_DATA.length; i++) {
    var row = SCENARIO_DATA[i];
    if (row[3] === horiz && row[6] === freq) {
      if (row[2] === univ && row[4] === strat && row[5] === weight) {
        matchedRows.push(row);
      }
    }
  }

  if (matchedRows.length === 0) {
    // Check if benchmark row match without strict weighting or universe constraint
    for (var b = 0; b < SCENARIO_DATA.length; b++) {
      var brow = SCENARIO_DATA[b];
      if (brow[3] === horiz && brow[6] === freq) {
        if (brow[4] === strat) {
          matchedRows.push(brow);
        }
      }
    }
  }

  if (matchedRows.length === 0) {
    return 'Scenario not found';
  }

  // Sort matched rows by tax rate ascending
  matchedRows.sort(function(a, b) {
    return a[1] - b[1];
  });

  // 1. Exact tier match within floating-point epsilon
  for (var j = 0; j < matchedRows.length; j++) {
    if (Math.abs(matchedRows[j][1] - rate) < 1e-5) {
      return matchedRows[j][colIdx];
    }
  }

  // 2. Piecewise linear interpolation between adjacent bounding empirical tiers
  var lowerRow = null;
  var upperRow = null;
  for (var k = 0; k < matchedRows.length; k++) {
    if (matchedRows[k][1] <= rate) {
      lowerRow = matchedRows[k];
    }
    if (matchedRows[k][1] >= rate && upperRow === null) {
      upperRow = matchedRows[k];
    }
  }

  if (!lowerRow && upperRow) {
    return upperRow[colIdx];
  }
  if (lowerRow && !upperRow) {
    return lowerRow[colIdx];
  }
  if (!lowerRow && !upperRow) {
    return 'Scenario not found';
  }

  var r1 = lowerRow[1];
  var r2 = upperRow[1];
  var v1 = lowerRow[colIdx];
  var v2 = upperRow[colIdx];

  if (Math.abs(r2 - r1) < 1e-7) {
    return v1;
  }

  return v1 + (rate - r1) * (v2 - v1) / (r2 - r1);
}

function getOrCreateSheet(ss, name) {
  var sheet = ss.getSheetByName(name);
  if (sheet) {
    sheet.clear();
    sheet.getRange(1, 1, sheet.getMaxRows(), sheet.getMaxColumns()).clearDataValidations();
    var charts = sheet.getCharts();
    for (var i = 0; i < charts.length; i++) {
      sheet.removeChart(charts[i]);
    }
  } else {
    sheet = ss.insertSheet(name);
  }
  return sheet;
}
