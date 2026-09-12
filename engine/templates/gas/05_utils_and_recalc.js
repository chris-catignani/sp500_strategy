
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
 * Custom formula to calculate estimated 30-year after-tax CAGR for an arbitrary tax rate.
 * @param {number|string} taxRate Tax rate as decimal (e.g. 0.30) or percentage ("30%").
 * @return {number|string} Estimated post-liquidation CAGR.
 * @customfunction
 */
function RECALCULATE_STRATEGY(taxRate) {
  var rate = (typeof taxRate === 'string') ? parseFloat(taxRate.replace('%', '')) / 100 : Number(taxRate);
  if (isNaN(rate) || rate < 0 || rate > 1) {
    return 'Invalid tax rate';
  }
  // Linear interpolation based on Top 5 30-year empirical results with dividends:
  // 0% -> 14.95%, 30% -> 12.04%
  var baseCagr = 0.1495;
  var drag = rate * 0.0970;
  return baseCagr - drag;
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
