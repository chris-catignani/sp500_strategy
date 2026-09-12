// ============================================================================
// COORDINATE CONTRACT WITH 01_scenario_data.js:
// References 'Scenario Data'! Era Matrix:       (Key: AH, Data: AI-AP)
// References 'Scenario Data'! Trajectory Matrix:(Key: T,  Data: U-Y)
// References 'Scenario Data'! Drawdown Matrix:  (Key: AA, Data: AB-AF)
// ============================================================================
// ==========================================
// Tab 2: Performance & Tradeoffs (Charts & Regimes)
// ==========================================
function buildPerformanceAndTradeoffsSheet(ss) {
  var sheet = getOrCreateSheet(ss, 'Performance & Tradeoffs');
  sheet.setHiddenGridlines(false);
  sheet.clearContents();

  // Explicit, proportional column widths across 14 columns (Cols A to N)
  var colWidths = [120, 95, 95, 85, 95, 95, 85, 90, 90, 95, 95, 105, 105, 130];
  for (var c = 0; c < colWidths.length; c++) {
    sheet.setColumnWidth(c + 1, colWidths[c]);
  }

  // 1. Banner Header (Row 1)
  sheet.getRange('A1:N1').merge()
       .setValue('S&P 500 & ALL-WORLD TOP N STRATEGY - HISTORICAL CHARTS & TRADEOFF ANALYSIS')
       .setBackground('#1B365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(14)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(1, 40);

  // 2. Subtitle Description (Row 2)
  sheet.getRange('A2:N2').merge()
       .setFormula('="Visualizing 30-year compounded wealth trajectories (" & TEXT(\'Executive Summary\'!$H$3, "$#,##0") & " initial basis), peak-to-trough drawdowns, and regime attribution for " & \'Executive Summary\'!$B$2 & " (" & \'Executive Summary\'!$B$3 & " rebalancing, 1994–2024)."')
       .setFontStyle('italic')
       .setFontColor('#4A5568')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(2, 24);
  sheet.setRowHeight(3, 10);

  // 3. Section 1: Historical Market Regime Attribution (5 Eras) (Rows 4 to 10)
  sheet.getRange('A4:H4').merge()
       .setValue('HISTORICAL MARKET REGIME ATTRIBUTION (5 ERAS)')
       .setBackground('#2C5282')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(11)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(4, 28);

  // Headers (Row 5)
  sheet.getRange('A5').setValue('Market Regime Era');
  sheet.getRange('B5').setValue('Historical Context / Regime');
  sheet.getRange('C5').setValue('Top 3 CAGR');
  sheet.getRange('D5').setValue('Top 5 CAGR');
  sheet.getRange('E5').setValue('Top 10 CAGR');
  sheet.getRange('F5').setFormula('="Benchmark (" & IF(\'Executive Summary\'!$B$2="All World", "MSCI World", "S&P 500") & ") CAGR"');
  sheet.getRange('G5').setFormula('="Top 10 Alpha vs " & IF(\'Executive Summary\'!$B$2="All World", "MSCI World", "SPX")');
  sheet.getRange('H5').setValue('Top 10 Win Rate');
  sheet.getRange('A5:H5')
       .setBackground('#2B6CB0')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(5, 26);

  // Spilled Data via FILTER formula in A6 (Rows 6 to 10)
  sheet.getRange('A6').setFormula(
    '=IFERROR(FILTER(\'Scenario Data\'!$AI$2:$AP$21, \'Scenario Data\'!$AH$2:$AH$21 = (\'Executive Summary\'!$B$2 & "_" & \'Executive Summary\'!$B$3)), "")'
  );

  for (var er = 0; er < 5; er++) {
    var rNum = 6 + er;
    var bg = (er === 4) ? '#EDF2F7' : ((er % 2 === 0) ? '#FFFFFF' : '#F7FAFC');
    sheet.getRange(rNum, 1, 1, 8).setBackground(bg);
    sheet.setRowHeight(rNum, 22);
  }

  sheet.getRange('A6:A10').setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('B6:B10').setVerticalAlignment('middle');
  sheet.getRange('C6:F10').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('G6:G10').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('H6:H10').setNumberFormat('0.0%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('A10:H10').setFontWeight('bold');
  sheet.getRange('A5:H10').setBorder(true, true, true, true, true, true, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  sheet.setRowHeight(11, 14);

  // 4. Section 2: Rebalancing Frequency Tradeoff Analysis Table (Rows 12 to 17)
  sheet.getRange('A12:N12').merge()
       .setFormula('="REBALANCING FREQUENCY TRADEOFF ANALYSIS — ANNUAL VS. QUARTERLY (" & \'Executive Summary\'!$B$2 & ", " & \'Executive Summary\'!$F$2 & ", " & \'Executive Summary\'!$H$2 & ", " & TEXT(\'Executive Summary\'!$F$3, "0.0%") & " TAX RATE)"')
       .setBackground('#2C5282')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(11)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(12, 28);

  var tradeoffHeaders = [
    'Strategy',
    'Annual Pre-Tax CAGR', 'Quarterly Pre-Tax CAGR', 'Pre-Tax Delta',
    'Annual Post-Liq CAGR', 'Quarterly Post-Liq CAGR', 'Net Post-Liq Delta',
    'Annual Max Drawdown', 'Quarterly Max Drawdown',
    'Annual Taxes Paid', 'Quarterly Taxes Paid',
    'Annual Ending Wealth', 'Quarterly Ending Wealth',
    'Frequency Advantage'
  ];
  sheet.getRange(13, 1, 1, tradeoffHeaders.length).setValues([tradeoffHeaders])
       .setBackground('#2D3748')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(9)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle')
       .setWrap(true);
  sheet.getRange('L13').setFormula('="Annual Wealth (" & TEXT(\'Executive Summary\'!$H$3, "$#,##0") & ")"');
  sheet.getRange('M13').setFormula('="Quarterly Wealth (" & TEXT(\'Executive Summary\'!$H$3, "$#,##0") & ")"');
  sheet.setRowHeight(13, 36);

  var taxExpr = 'IF(ISNUMBER(\'Executive Summary\'!$F$3), TEXT(\'Executive Summary\'!$F$3, "0.0%"), \'Executive Summary\'!$F$3)';
  var stratRows = [
    ['Top 3 Strategy', 'Top 3'],
    ['Top 5 Strategy', 'Top 5'],
    ['Top 10 Strategy', 'Top 10'],
    ['Benchmark', 'Benchmark']
  ];

  for (var si = 0; si < stratRows.length; si++) {
    var trRow = 14 + si;
    var sDisplay = stratRows[si][0];
    var sCode = stratRows[si][1];

    var annKey, qtrKey;
    if (sCode === 'Benchmark') {
      sheet.getRange('A' + trRow).setFormula('="Benchmark (" & IF(\'Executive Summary\'!$B$2="All World", "MSCI World", "S&P 500") & ")"');
      annKey = '\'Executive Summary\'!$H$2 & "_" & IF(\'Executive Summary\'!$B$2="All World", "All World_MSCI World_Annual_", "S&P 500_S&P 500_Annual_") & ' + taxExpr;
      qtrKey = '\'Executive Summary\'!$H$2 & "_" & IF(\'Executive Summary\'!$B$2="All World", "All World_MSCI World_Quarterly_", "S&P 500_S&P 500_Quarterly_") & ' + taxExpr;
    } else {
      sheet.getRange('A' + trRow).setValue(sDisplay);
      annKey = '\'Executive Summary\'!$H$2 & "_" & \'Executive Summary\'!$B$2 & "_' + sCode + '_" & \'Executive Summary\'!$F$2 & "_Annual_" & ' + taxExpr;
      qtrKey = '\'Executive Summary\'!$H$2 & "_" & \'Executive Summary\'!$B$2 & "_' + sCode + '_" & \'Executive Summary\'!$F$2 & "_Quarterly_" & ' + taxExpr;
    }

    // Col B: Annual Pre-Tax CAGR (Col H in Scenario Data)
    sheet.getRange('B' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$H:$H, MATCH(' + annKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col C: Quarterly Pre-Tax CAGR
    sheet.getRange('C' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$H:$H, MATCH(' + qtrKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col D: Pre-Tax Delta
    sheet.getRange('D' + trRow).setFormula('=C' + trRow + ' - B' + trRow);
    // Col E: Annual Post-Liq CAGR (Col J in Scenario Data)
    sheet.getRange('E' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$J:$J, MATCH(' + annKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col F: Quarterly Post-Liq CAGR
    sheet.getRange('F' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$J:$J, MATCH(' + qtrKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col G: Net Post-Liq Delta
    sheet.getRange('G' + trRow).setFormula('=F' + trRow + ' - E' + trRow);
    // Col H: Annual Max Drawdown (Col N in Scenario Data)
    sheet.getRange('H' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$N:$N, MATCH(' + annKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col I: Quarterly Max Drawdown
    sheet.getRange('I' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$N:$N, MATCH(' + qtrKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col J: Annual Total Taxes (Col O in Scenario Data)
    sheet.getRange('J' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$O:$O, MATCH(' + annKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col K: Quarterly Total Taxes
    sheet.getRange('K' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$O:$O, MATCH(' + qtrKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col L: Annual Ending Wealth (Col L in Scenario Data)
    sheet.getRange('L' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$L:$L, MATCH(' + annKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col M: Quarterly Ending Wealth
    sheet.getRange('M' + trRow).setFormula('=IFERROR(INDEX(\'Scenario Data\'!$L:$L, MATCH(' + qtrKey + ', \'Scenario Data\'!$A:$A, 0)), 0)');
    // Col N: Frequency Advantage Verdict
    sheet.getRange('N' + trRow).setFormula('=IF(G' + trRow + ' > 0.0005, "Quarterly Outperformance", IF(G' + trRow + ' < -0.0005, "Annual Tax-Efficiency", "Neutral / Parity"))');

    sheet.setRowHeight(trRow, 24);
  }

  sheet.getRange('A14:A17').setFontWeight('bold').setVerticalAlignment('middle');
  sheet.getRange('B14:C17').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('D14:D17').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('E14:F17').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('G14:G17').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('H14:I17').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('J14:K17').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('L14:M17').setNumberFormat('$#,##0.00').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('N14:N17').setFontStyle('italic').setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');

  sheet.getRange('A14:N14').setBackground('#FFFFFF');
  sheet.getRange('A15:N15').setBackground('#F7FAFC');
  sheet.getRange('A16:N16').setBackground('#FFFFFF');
  sheet.getRange('A17:N17').setBackground('#EDF2F7');
  sheet.getRange('A13:N17').setBorder(true, true, true, true, true, true, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  for (var sr = 18; sr <= 20; sr++) {
    sheet.setRowHeight(sr, 12);
  }
  for (var cr = 21; cr <= 39; cr++) {
    sheet.setRowHeight(cr, 20);
  }
  sheet.setRowHeight(40, 14);

  // 5. Section 3: Section Titles & Table Headers for Time Series Data (Rows 41 & 42)
  sheet.getRange('A41:E41').merge()
       .setFormula('="30-YEAR WEALTH ACCUMULATION DATA (" & TEXT(\'Executive Summary\'!$H$3, "$#,##0") & " BASIS)"')
       .setBackground('#2C5282')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');

  sheet.getRange('G41:K41').merge()
       .setValue('HISTORICAL DRAWDOWN FROM PEAK DATA')
       .setBackground('#2C5282')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(41, 26);

  // Table Headers (Row 42)
  sheet.getRange('A42').setValue('Year');
  sheet.getRange('B42').setValue('Top 3 ($)');
  sheet.getRange('C42').setValue('Top 5 ($)');
  sheet.getRange('D42').setValue('Top 10 ($)');
  sheet.getRange('E42').setFormula('="Benchmark (" & IF(\'Executive Summary\'!$B$2="All World", "MSCI World", "S&P 500") & ")"');
  sheet.getRange('A42:E42')
       .setBackground('#4A5568')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');

  sheet.getRange('G42').setValue('Year');
  sheet.getRange('H42').setValue('Top 3 Drawdown');
  sheet.getRange('I42').setValue('Top 5 Drawdown');
  sheet.getRange('J42').setValue('Top 10 Drawdown');
  sheet.getRange('K42').setFormula('="Benchmark (" & IF(\'Executive Summary\'!$B$2="All World", "MSCI World", "S&P 500") & ") Drawdown"');
  sheet.getRange('G42:K42')
       .setBackground('#4A5568')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(42, 24);

  // 6. Section 4: Time Series Data Rows (Rows 43 to 73, 31 years)
  // Dynamic spilled FILTER formulas
  sheet.getRange('A43').setFormula(
    '=FILTER(\'Scenario Data\'!$U$2:$Y$125, \'Scenario Data\'!$T$2:$T$125 = (\'Executive Summary\'!$B$2 & "_" & \'Executive Summary\'!$B$3))'
  );
  sheet.getRange('G43').setFormula(
    '=FILTER(\'Scenario Data\'!$AB$2:$AF$125, \'Scenario Data\'!$AA$2:$AA$125 = (\'Executive Summary\'!$B$2 & "_" & \'Executive Summary\'!$B$3))'
  );

  // Formatting Trajectory Table (Rows 43 to 73)
  sheet.getRange(43, 1, 31, 1).setNumberFormat('####').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange(43, 2, 31, 4).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(42, 1, 32, 5).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);

  // Formatting Drawdown Table (Rows 43 to 73)
  sheet.getRange(43, 7, 31, 1).setNumberFormat('####').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange(43, 8, 31, 4).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(42, 7, 32, 5).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);

  for (var tr = 0; tr < 31; tr++) {
    var rowN = 43 + tr;
    var bgRow = (tr % 2 === 0) ? '#FFFFFF' : '#F7FAFC';
    sheet.getRange(rowN, 1, 1, 5).setBackground(bgRow);
    sheet.getRange(rowN, 7, 1, 5).setBackground(bgRow);
    sheet.setRowHeight(rowN, 20);
  }

  // Flush all cell values and formats to spreadsheet before creating charts
  SpreadsheetApp.flush();

  // 7. Embedded Native Charts (Rows 21 to 39)
  // Chart 1: Growth of Seed Capital Line Chart (Logarithmic Scale)
  var growthRange = sheet.getRange(42, 1, 32, 5);
  var growthChart = sheet.newChart()
    .asLineChart()
    .addRange(growthRange)
    .setNumHeaders(1)
    .useLogScale()
    .setOption('useFirstColumnAsDomain', true)
    .setOption('title', 'Growth of Seed Capital (Log Scale, 1994–2024)')
    .setOption('titleTextStyle', {fontSize: 13, bold: true, color: '#1A202C'})
    .setOption('legend', {position: 'top', textStyle: {fontSize: 10}})
    .setOption('hAxis', {title: 'Year', format: '####', gridlines: {count: 8}})
    .setOption('vAxis', {title: 'Portfolio Value ($) - Log Scale', scaleType: 'log', logScale: true, format: '$#,##0'})
    .setOption('vAxes.0.logScale', true)
    .setOption('vAxes.0.scaleType', 'log')
    .setOption('vAxes.0.title', 'Portfolio Value ($) - Log Scale')
    .setOption('vAxis.logScale', true)
    .setOption('vAxis.scaleType', 'log')
    .setOption('vAxis.title', 'Portfolio Value ($) - Log Scale')
    .setOption('colors', ['#805AD5', '#2B6CB0', '#285E61', '#A0AEC0'])
    .setOption('width', 590)
    .setOption('height', 370)
    .setPosition(21, 1, 0, 0)
    .build();
  sheet.insertChart(growthChart);

  // Chart 2: Historical Drawdowns from Peak Line Chart
  var ddRange = sheet.getRange(42, 7, 32, 5);
  var ddChart = sheet.newChart()
    .asLineChart()
    .addRange(ddRange)
    .setNumHeaders(1)
    .setOption('useFirstColumnAsDomain', true)
    .setOption('title', 'Historical Drawdown from Peak (1994–2024)')
    .setOption('titleTextStyle', {fontSize: 13, bold: true, color: '#1A202C'})
    .setOption('legend', {position: 'top', textStyle: {fontSize: 10}})
    .setOption('hAxis', {title: 'Year', format: '####', gridlines: {count: 8}})
    .setOption('vAxis', {title: 'Drawdown (%)', format: '0.0%'})
    .setOption('colors', ['#805AD5', '#2B6CB0', '#285E61', '#A0AEC0'])
    .setOption('width', 590)
    .setOption('height', 370)
    .setPosition(21, 7, 0, 0)
    .build();
  sheet.insertChart(ddChart);
}

