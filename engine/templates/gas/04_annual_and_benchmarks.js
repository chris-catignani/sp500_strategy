// ==========================================
// Strategy Tabs (Top 3, Top 5, Top 10)
// ==========================================
function buildAnnualSheet(ss, sheetName, annualData) {
  var sheet = getOrCreateSheet(ss, sheetName);
  sheet.setHiddenGridlines(false);

  var decoratedAnnual = [];
  var dollarCols = [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
  for (var r = 0; r < annualData.length; r++) {
    var arow = annualData[r].slice();
    for (var d = 0; d < dollarCols.length; d++) {
      var cIdx = dollarCols[d];
      arow[cIdx] = '=' + arow[cIdx] + ' * ' + SCALE_EXPR;
    }
    decoratedAnnual.push(arow);
  }
  var rows = [ANNUAL_HEADERS].concat(decoratedAnnual);
  sheet.getRange(1, 1, rows.length, ANNUAL_HEADERS.length).setValues(rows);

  // Header Styling
  var headerRange = sheet.getRange(1, 1, 1, ANNUAL_HEADERS.length);
  headerRange.setBackground('#1B365D')
             .setFontColor('#FFFFFF')
             .setFontWeight('bold')
             .setHorizontalAlignment('center')
             .setVerticalAlignment('middle')
             .setWrap(true);

  sheet.setRowHeight(1, 36);

  if (annualData.length > 0) {
    // Col 1: Year
    sheet.getRange(2, 1, annualData.length, 1).setNumberFormat('#,##0').setHorizontalAlignment('center').setVerticalAlignment('middle');
    // Col 2: Start Value
    sheet.getRange(2, 2, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 3: Gross Return
    sheet.getRange(2, 3, annualData.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 4: Dividends Received ($)
    sheet.getRange(2, 4, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 5: Pre-Tax Ending Value
    sheet.getRange(2, 5, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 6: Realized Capital Gain
    sheet.getRange(2, 6, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 7: Net Taxable Gain
    sheet.getRange(2, 7, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 8: Capital Gains Tax ($)
    sheet.getRange(2, 8, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 9: Dividend Tax ($)
    sheet.getRange(2, 9, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 10: Total Tax Paid ($)
    sheet.getRange(2, 10, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 11: Loss Carryforward
    sheet.getRange(2, 11, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 12: Ending Value (After-Tax)
    sheet.getRange(2, 12, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 13: Cash Reserve
    sheet.getRange(2, 13, annualData.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 14: SPX Return
    sheet.getRange(2, 14, annualData.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
    // Col 15: Turnover
    sheet.getRange(2, 15, annualData.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');

    // Alternating rows
    for (var r = 0; r < annualData.length; r++) {
      var bg = (r % 2 === 0) ? '#FFFFFF' : '#F7FAFC';
      sheet.getRange(2 + r, 1, 1, ANNUAL_HEADERS.length).setBackground(bg);
      sheet.setRowHeight(2 + r, 22);
    }
    sheet.getRange(1, 1, annualData.length + 1, ANNUAL_HEADERS.length).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);
  }

  var annualColWidths = [70, 110, 95, 115, 115, 115, 110, 110, 105, 105, 110, 120, 100, 95, 90];
  for (var ac = 0; ac < annualColWidths.length; ac++) {
    sheet.setColumnWidth(ac + 1, annualColWidths[ac]);
  }
  sheet.setFrozenRows(1);
}

// ==========================================
// Benchmark Tab: S&P 500 Benchmark
// ==========================================
function buildBenchmarkSheet(ss) {
  var sheet = getOrCreateSheet(ss, 'S&P 500 Benchmark');
  sheet.setHiddenGridlines(false);

  var decoratedSPX = [];
  for (var s = 0; s < SPX_DATA.length; s++) {
    var srow = [SPX_DATA[s][0], SPX_DATA[s][1], SPX_DATA[s][2], '=' + SPX_DATA[s][3] + ' * ' + SCALE_EXPR];
    decoratedSPX.push(srow);
  }
  var rows = [SPX_HEADERS].concat(decoratedSPX);
  sheet.getRange(1, 1, rows.length, SPX_HEADERS.length).setValues(rows);
  sheet.getRange('D1').setFormula('="Compounded Growth (" & TEXT(\'Executive Summary\'!$H$3, "$#,##0") & " Invested)"');

  // Header Styling
  var headerRange = sheet.getRange(1, 1, 1, SPX_HEADERS.length);
  headerRange.setBackground('#1B365D')
             .setFontColor('#FFFFFF')
             .setFontWeight('bold')
             .setHorizontalAlignment('center')
             .setVerticalAlignment('middle')
             .setWrap(true);

  sheet.setRowHeight(1, 36);

  if (SPX_DATA.length > 0) {
    sheet.getRange(2, 1, SPX_DATA.length, 1).setNumberFormat('#,##0').setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 2, SPX_DATA.length, 1).setNumberFormat('#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    sheet.getRange(2, 3, SPX_DATA.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
    sheet.getRange(2, 4, SPX_DATA.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');

    for (var r = 0; r < SPX_DATA.length; r++) {
      var bg = (r % 2 === 0) ? '#FFFFFF' : '#F7FAFC';
      sheet.getRange(2 + r, 1, 1, SPX_HEADERS.length).setBackground(bg);
      sheet.setRowHeight(2 + r, 22);
    }
    sheet.getRange(1, 1, SPX_DATA.length + 1, SPX_HEADERS.length).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);
  }

  var spxColWidths = [80, 115, 140, 175];
  for (var sc = 0; sc < spxColWidths.length; sc++) {
    sheet.setColumnWidth(sc + 1, spxColWidths[sc]);
  }
  sheet.setFrozenRows(1);
}

// ==========================================
// Tab 6: Historical Holdings & Trades
// ==========================================
function buildTradesSheet(ss) {
  var sheet = getOrCreateSheet(ss, 'Historical Holdings & Trades');
  sheet.setHiddenGridlines(false);

  var rows = [TRADE_HEADERS].concat(TRADE_DATA);
  sheet.getRange(1, 1, rows.length, TRADE_HEADERS.length).setValues(rows);

  // Header Styling
  var headerRange = sheet.getRange(1, 1, 1, TRADE_HEADERS.length);
  headerRange.setBackground('#1B365D')
             .setFontColor('#FFFFFF')
             .setFontWeight('bold')
             .setHorizontalAlignment('center')
             .setVerticalAlignment('middle')
             .setWrap(true);

  sheet.setRowHeight(1, 36);

  if (TRADE_DATA.length > 0) {
    sheet.getRange(2, 1, TRADE_DATA.length, 1).setNumberFormat('#,##0').setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 2, TRADE_DATA.length, 1).setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 3, TRADE_DATA.length, 1).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 4, TRADE_DATA.length, 1).setHorizontalAlignment('center').setVerticalAlignment('middle');
    sheet.getRange(2, 5, TRADE_DATA.length, 1).setNumberFormat('#,##0.0000').setHorizontalAlignment('right').setVerticalAlignment('middle');
    sheet.getRange(2, 6, TRADE_DATA.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
    sheet.getRange(2, 7, TRADE_DATA.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');

    for (var r = 0; r < TRADE_DATA.length; r++) {
      var bg = (r % 2 === 0) ? '#FFFFFF' : '#F7FAFC';
      sheet.getRange(2 + r, 1, 1, TRADE_HEADERS.length).setBackground(bg);
      sheet.setRowHeight(2 + r, 20);
    }
    sheet.getRange(1, 1, TRADE_DATA.length + 1, TRADE_HEADERS.length).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);
  }

  var tradeColWidths = [75, 140, 85, 80, 110, 125, 125];
  for (var tc = 0; tc < tradeColWidths.length; tc++) {
    sheet.setColumnWidth(tc + 1, tradeColWidths[tc]);
  }
  sheet.setFrozenRows(1);
}

