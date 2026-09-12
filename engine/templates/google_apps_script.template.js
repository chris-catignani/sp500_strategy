/**
 * Google Apps Script for S&P 500 & All-World Top N Strategy Interactive Dashboard
 * Generated automatically by engine/exporters/apps_script.py
 *
 * Instructions:
 * 1. Open your Google Sheet.
 * 2. Go to Extensions > Apps Script.
 * 3. Replace all text in Code.gs with this script.
 * 4. Save and return to Google Sheets.
 * 5. Refresh the sheet, then click the new menu: "S&P 500 & World Strategy" > "Build All Sheets".
 */

// ==========================================
// Embedded Simulation Data
// ==========================================
var BASE_INITIAL_CAPITAL = /*__BASE_INITIAL_CAPITAL__*/10000;
var SCALE_EXPR = "(IF(AND(ISNUMBER('Executive Summary'!$N$2), 'Executive Summary'!$N$2 > 0), 'Executive Summary'!$N$2, " + BASE_INITIAL_CAPITAL + ") / " + BASE_INITIAL_CAPITAL + ")";

var SCENARIO_HEADERS = [
  "LookupKey", "TaxRate", "Universe", "Horizon", "Strategy", "Frequency", "PreTaxCAGR",
  "AfterTaxCAGR", "PostLiqCAGR", "CumReturn", "FinalEquity",
  "TotalDividends", "MaxDD", "TotalTaxes", "TaxDrag", "Alpha", "RowType"
];
var SCENARIO_DATA = /*__SCENARIO_DATA__*/[];

var ANNUAL_HEADERS = [
  "Year", "Start Value", "Gross Return", "Dividends Received ($)", "Ending Value (Pre-Tax)",
  "Realized Capital Gain", "Net Taxable Gain", "Capital Gains Tax ($)", "Dividend Tax ($)",
  "Total Tax Paid ($)", "Loss Carryforward", "Ending Value (After-Tax)", "Cash Reserve",
  "S&P 500 Return", "Annual Turnover"
];
var TOP3_ANNUAL_DATA = /*__TOP3_ANNUAL_DATA__*/[];
var TOP5_ANNUAL_DATA = /*__TOP5_ANNUAL_DATA__*/[];
var TOP10_ANNUAL_DATA = /*__TOP10_ANNUAL_DATA__*/[];
var WORLD_TOP3_ANNUAL_DATA = /*__WORLD_TOP3_ANNUAL_DATA__*/[];
var WORLD_TOP5_ANNUAL_DATA = /*__WORLD_TOP5_ANNUAL_DATA__*/[];
var WORLD_TOP10_ANNUAL_DATA = /*__WORLD_TOP10_ANNUAL_DATA__*/[];

var SPX_HEADERS = ["Year", "S&P 500 Level", "Annual Return", "Compounded Growth"];
var SPX_DATA = /*__SPX_DATA__*/[];

var TRADE_HEADERS = ["Year", "Strategy", "Ticker", "Action", "Shares", "Execution Price", "Realized Gain"];
var TRADE_DATA = /*__TRADE_DATA__*/[];

var ERA_HEADERS = [
  "Market Regime Era", "Historical Context / Regime", "Top 3 CAGR", "Top 5 CAGR",
  "Top 10 CAGR", "S&P 500 CAGR", "Top 10 Alpha vs SPX", "Top 10 Win Rate"
];
var ERA_DATA = /*__ERA_DATA__*/[];

var TRAJECTORY_HEADERS = ["Year", "Top 3 ($)", "Top 5 ($)", "Top 10 ($)", "S&P 500 ($)"];
var TRAJECTORY_DATA = /*__TRAJECTORY_DATA__*/[];

var DRAWDOWN_HEADERS = ["Year", "Top 3 Drawdown", "Top 5 Drawdown", "Top 10 Drawdown", "S&P 500 Drawdown"];
var DRAWDOWN_DATA = /*__DRAWDOWN_DATA__*/[];

// ==========================================
// Google Sheets UI & Menu Triggers
// ==========================================
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('S&P 500 & World Strategy')
    .addItem('Build All Sheets', 'buildAllSheets')
    .addSeparator()
    .addItem('Show S&P 500 Tabs Only', 'filterTabsSP500')
    .addItem('Show All World Tabs Only', 'filterTabsWorld')
    .addItem('Show All Tabs', 'filterTabsAll')
    .addSeparator()
    .addItem('Recalculate Sheet', 'recalculateSheet')
    .addToUi();
}

function filterTabsSP500() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var worldTabs = ['World Top 3 Strategy', 'World Top 5 Strategy', 'World Top 10 Strategy'];
  for (var i = 0; i < worldTabs.length; i++) {
    var s = ss.getSheetByName(worldTabs[i]);
    if (s) s.hideSheet();
  }
  var spTabs = ['Executive Summary', 'Performance & Tradeoffs', 'Top 3 Strategy', 'Top 5 Strategy', 'Top 10 Strategy', 'S&P 500 Benchmark', 'Historical Holdings & Trades', 'Scenario Data'];
  for (var j = 0; j < spTabs.length; j++) {
    var s2 = ss.getSheetByName(spTabs[j]);
    if (s2) s2.showSheet();
  }
  ss.toast('Filtered to S&P 500 strategy tabs.', 'Filter Tabs', 3);
}

function filterTabsWorld() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var spTabs = ['Top 3 Strategy', 'Top 5 Strategy', 'Top 10 Strategy'];
  for (var i = 0; i < spTabs.length; i++) {
    var s = ss.getSheetByName(spTabs[i]);
    if (s) s.hideSheet();
  }
  var worldTabs = ['Executive Summary', 'Performance & Tradeoffs', 'World Top 3 Strategy', 'World Top 5 Strategy', 'World Top 10 Strategy', 'S&P 500 Benchmark', 'Historical Holdings & Trades', 'Scenario Data'];
  for (var j = 0; j < worldTabs.length; j++) {
    var s2 = ss.getSheetByName(worldTabs[j]);
    if (s2) s2.showSheet();
  }
  ss.toast('Filtered to All World strategy tabs.', 'Filter Tabs', 3);
}

function filterTabsAll() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var allTabs = [
    'Executive Summary', 'Performance & Tradeoffs',
    'Top 3 Strategy', 'Top 5 Strategy', 'Top 10 Strategy',
    'World Top 3 Strategy', 'World Top 5 Strategy', 'World Top 10 Strategy',
    'S&P 500 Benchmark', 'Historical Holdings & Trades', 'Scenario Data'
  ];
  for (var i = 0; i < allTabs.length; i++) {
    var s = ss.getSheetByName(allTabs[i]);
    if (s) s.showSheet();
  }
  ss.toast('All tabs are now visible.', 'Filter Tabs', 3);
}

// ==========================================
// Primary Build Coordinator
// ==========================================
function buildAllSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // 1. Scenario Data Tab
  buildScenarioDataSheet(ss);

  // 2. Executive Summary Dashboard Tab
  buildExecutiveSummarySheet(ss);

  // 3. Performance & Tradeoffs Tab (Charts & Regime Attribution)
  buildPerformanceAndTradeoffsSheet(ss);

  // 4. S&P 500 Strategy Tabs
  buildAnnualSheet(ss, 'Top 3 Strategy', TOP3_ANNUAL_DATA);
  buildAnnualSheet(ss, 'Top 5 Strategy', TOP5_ANNUAL_DATA);
  buildAnnualSheet(ss, 'Top 10 Strategy', TOP10_ANNUAL_DATA);

  // 5. All-World Strategy Tabs
  buildAnnualSheet(ss, 'World Top 3 Strategy', WORLD_TOP3_ANNUAL_DATA);
  buildAnnualSheet(ss, 'World Top 5 Strategy', WORLD_TOP5_ANNUAL_DATA);
  buildAnnualSheet(ss, 'World Top 10 Strategy', WORLD_TOP10_ANNUAL_DATA);

  // 6. Benchmark Tab
  buildBenchmarkSheet(ss);

  // 7. Holdings & Trades Tab
  buildTradesSheet(ss);

  // Organize tab order: Executive Summary is always tab 1
  var tabOrder = [
    'Executive Summary',
    'Performance & Tradeoffs',
    'Top 3 Strategy',
    'Top 5 Strategy',
    'Top 10 Strategy',
    'World Top 3 Strategy',
    'World Top 5 Strategy',
    'World Top 10 Strategy',
    'S&P 500 Benchmark',
    'Historical Holdings & Trades',
    'Scenario Data'
  ];
  for (var i = 0; i < tabOrder.length; i++) {
    var sheet = ss.getSheetByName(tabOrder[i]);
    if (sheet) {
      ss.setActiveSheet(sheet);
      ss.moveActiveSheet(i + 1);
    }
  }

  // Activate Executive Summary
  var execSheet = ss.getSheetByName('Executive Summary');
  if (execSheet) {
    ss.setActiveSheet(execSheet);
  }

  SpreadsheetApp.flush();
  ss.toast('All sheets successfully created and styled!', 'Build Complete', 4);
}

// ==========================================
// Tab 1: Scenario Data (Lookup Engine)
// ==========================================
function buildScenarioDataSheet(ss) {
  var sheet = getOrCreateSheet(ss, 'Scenario Data');
  sheet.setHiddenGridlines(false);

  var decoratedData = [];
  for (var i = 0; i < SCENARIO_DATA.length; i++) {
    var r = SCENARIO_DATA[i].slice();
    r[10] = '=' + r[10] + ' * ' + SCALE_EXPR;
    r[11] = '=' + r[11] + ' * ' + SCALE_EXPR;
    r[13] = '=' + r[13] + ' * ' + SCALE_EXPR;
    decoratedData.push(r);
  }
  var rows = [SCENARIO_HEADERS].concat(decoratedData);
  sheet.getRange(1, 1, rows.length, SCENARIO_HEADERS.length).setValues(rows);

  // Header Styling
  var headerRange = sheet.getRange(1, 1, 1, SCENARIO_HEADERS.length);
  headerRange.setBackground('#1B365D')
             .setFontColor('#FFFFFF')
             .setFontWeight('bold')
             .setHorizontalAlignment('center');

  // Number Formatting (17 columns)
  if (SCENARIO_DATA.length > 0) {
    sheet.getRange(2, 1, SCENARIO_DATA.length, 1).setHorizontalAlignment('left');
    sheet.getRange(2, 2, SCENARIO_DATA.length, 1).setNumberFormat('0.0%').setHorizontalAlignment('center');
    sheet.getRange(2, 3, SCENARIO_DATA.length, 2).setHorizontalAlignment('center');
    sheet.getRange(2, 5, SCENARIO_DATA.length, 1).setHorizontalAlignment('left');
    sheet.getRange(2, 6, SCENARIO_DATA.length, 1).setHorizontalAlignment('center');
    sheet.getRange(2, 7, SCENARIO_DATA.length, 4).setNumberFormat('0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 11, SCENARIO_DATA.length, 2).setNumberFormat('$#,##0.00').setHorizontalAlignment('right');
    sheet.getRange(2, 13, SCENARIO_DATA.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 14, SCENARIO_DATA.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right');
    sheet.getRange(2, 15, SCENARIO_DATA.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 16, SCENARIO_DATA.length, 1).setNumberFormat('+0.00%;-0.00%;0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 17, SCENARIO_DATA.length, 1).setHorizontalAlignment('center');
  }

  sheet.autoResizeColumns(1, SCENARIO_HEADERS.length);
  sheet.setFrozenRows(1);
}

// ==========================================
// Tab 2: Executive Summary Dashboard
// ==========================================
function buildExecutiveSummarySheet(ss) {
  var sheet = getOrCreateSheet(ss, 'Executive Summary');
  sheet.setHiddenGridlines(false);

  // 1. Banner Header (A1:N1, 14 columns)
  sheet.getRange('A1:N1').merge()
       .setValue('S&P 500 & ALL-WORLD TOP N STRATEGY — EXECUTIVE DASHBOARD')
       .setBackground('#1B365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(14)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle')
       .setWrapStrategy(SpreadsheetApp.WrapStrategy.OVERFLOW);

  // 2. Interactive Parameter Dropdowns in Row 2 (7 Controls across 14 columns)
  // Clear any existing data validation rules from previous builds
  sheet.getRange('A2:N2').clearDataValidations();

  // Control 1: Universe (Cols A-B)
  sheet.getRange('A2').setValue('Universe:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var b2 = sheet.getRange('B2');
  var univRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['S&P 500', 'All World'], true)
    .setAllowInvalid(false)
    .build();
  b2.setDataValidation(univRule);
  b2.setValue('S&P 500')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 2: Strategy (Cols C-D)
  sheet.getRange('C2').setValue('Strategy:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var d2 = sheet.getRange('D2');
  var stratRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['Top 3', 'Top 5', 'Top 10'], true)
    .setAllowInvalid(false)
    .build();
  d2.setDataValidation(stratRule);
  d2.setValue('Top 5')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 3: Horizon (Cols E-F)
  sheet.getRange('E2').setValue('Horizon:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var f2 = sheet.getRange('F2');
  var horizRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['10y', '20y', '30y'], true)
    .setAllowInvalid(false)
    .build();
  f2.setDataValidation(horizRule);
  f2.setValue('30y')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 4: Rebalance Frequency (Cols G-H)
  sheet.getRange('G2').setValue('Rebalance:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var h2 = sheet.getRange('H2');
  var freqRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['Annual', 'Quarterly'], true)
    .setAllowInvalid(false)
    .build();
  h2.setDataValidation(freqRule);
  h2.setValue('Annual')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 5: Benchmark (Cols I-J)
  sheet.getRange('I2').setValue('Benchmark:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var j2 = sheet.getRange('J2');
  var benchRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['S&P 500', 'MSCI World'], true)
    .setAllowInvalid(false)
    .build();
  j2.setDataValidation(benchRule);
  j2.setValue('S&P 500')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 6: Tax Rate (Cols K-L)
  sheet.getRange('K2').setValue('Tax Rate:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var l2 = sheet.getRange('L2');
  var taxRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['0.0%', '15.0%', '20.0%', '30.0%', '37.0%'], true)
    .setAllowInvalid(false)
    .build();
  l2.setDataValidation(taxRule);
  l2.setValue(0.30)
    .setNumberFormat('0.0%')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 7: Seed Capital (Cols M-N)
  sheet.getRange('M2').setValue('Seed Capital:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var n2 = sheet.getRange('N2');
  var seedRule = SpreadsheetApp.newDataValidation()
    .requireNumberGreaterThan(0)
    .setAllowInvalid(false)
    .setHelpText('Please enter a positive seed investment amount.')
    .build();
  n2.setDataValidation(seedRule);
  n2.setValue(BASE_INITIAL_CAPITAL)
    .setNumberFormat('$#,##0')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Helper expressions for Scenario Data lookups with string-resilient tax rate formatting
  var taxExpr = 'IF(ISNUMBER($L$2), TEXT($L$2, "0.0%"), $L$2)';
  var stratKeyExpr = '$F$2 & "_" & $B$2 & "_" & $D$2 & "_" & $H$2 & "_" & ' + taxExpr;
  var benchKeyExpr = '$F$2 & "_" & IF($J$2="MSCI World", "All World_MSCI World", "S&P 500_S&P 500") & "_" & $H$2 & "_" & ' + taxExpr;

  // 3. Dynamic KPI Summary Scorecards (Rows 4-6)
  // Card 1: Selected Strategy Final Wealth (Cols A-C)
  sheet.getRange('A4:C4').merge().setFormula('=$D$2 & " Final Wealth (" & $F$2 & ")"').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A5:C5').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$K:$K, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#22543D').setNumberFormat('$#,##0.00').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A6:C6').merge().setFormula('="After all taxes (" & TEXT($N$2, "$#,##0") & " start)"').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A4:C6').setBackground('#E6FFFA').setBorder(true, true, true, true, false, false, '#B2F5EA', SpreadsheetApp.BorderStyle.SOLID);

  // Card 2: Selected Benchmark Wealth (Cols D-F)
  sheet.getRange('D4:F4').merge().setFormula('=$J$2 & " Wealth (" & $F$2 & ")"').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D5:F5').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$K:$K, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#4A5568').setNumberFormat('$#,##0.00').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D6:F6').merge().setValue('Passive buy & hold').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D4:F6').setBackground('#EDF2F7').setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // Card 3: Selected Strategy Post-Liquidation CAGR (Cols G-H)
  sheet.getRange('G4:H4').merge().setFormula('="Post-Liq CAGR (" & $D$2 & ")"').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('G5:H5').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#1B365D').setNumberFormat('0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('G6:H6').merge().setValue('Net after-tax annual rate').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('G4:H6').setBackground('#EBF8FF').setBorder(true, true, true, true, false, false, '#BEE3F8', SpreadsheetApp.BorderStyle.SOLID);

  // Card 4: Annual Alpha vs Selected Benchmark (Cols I-K)
  sheet.getRange('I4:K4').merge().setFormula('="Annual Alpha vs " & $J$2').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('I5:K5').merge().setFormula('=(IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0) - IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0))').setFontWeight('bold').setFontSize(14).setFontColor('#22543D').setNumberFormat('+0.00%;-0.00%;0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('I6:K6').merge().setValue('Excess annual compound return').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('I4:K6').setBackground('#F0FFF4').setBorder(true, true, true, true, false, false, '#C6F6D5', SpreadsheetApp.BorderStyle.SOLID);

  // Card 5: Selected Strategy Annual Tax Drag (Cols L-N)
  sheet.getRange('L4:N4').merge().setFormula('="Annual Tax Drag (" & $D$2 & ")"').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('L5:N5').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$O:$O, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#9B2C2C').setNumberFormat('0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('L6:N6').merge().setValue('Annual return lost to taxes').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('L4:N6').setBackground('#FFF5F5').setBorder(true, true, true, true, false, false, '#FED7D7', SpreadsheetApp.BorderStyle.SOLID);

  // 4. Head-to-Head Scenario Spotlight Table (Rows 8-12)
  // Row 8: Title Banner
  sheet.getRange('A8:N8').merge()
       .setValue('HEAD-TO-HEAD PERFORMANCE & TAX SPOTLIGHT')
       .setBackground('#1B365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(11)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');

  // Row 9: Table Header (14 columns)
  var tableHeaders = [
    'Role / Selection', 'Universe', 'Horizon', 'Frequency', 'Annual Return (Pre-Tax)', 'Annual Return (After-Tax)', 'Annual Return (Post-Liq)',
    'Total Return (Cumulative)', 'Ending Wealth', 'Total Dividends Received',
    'Max Drawdown (Worst Drop)', 'Total Taxes Paid', 'Annual Tax Drag', 'Excess vs Benchmark (Alpha)'
  ];
  sheet.getRange(9, 1, 1, tableHeaders.length).setValues([tableHeaders])
       .setBackground('#2D3748')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(9)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle')
       .setWrap(true);
  sheet.getRange('I9').setFormula('="Ending Wealth (" & TEXT($N$2, "$#,##0") & " Start)"');

  // Row 10: Selected Strategy Row (INDEX/MATCH from Scenario Data Cols G-P mapped to E-N)
  sheet.getRange('A10').setFormula('="★ Strategy: " & $D$2').setFontWeight('bold').setHorizontalAlignment('left').setVerticalAlignment('middle');
  sheet.getRange('B10').setFormula('=$B$2').setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C10').setFormula('=$F$2').setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D10').setFormula('=$H$2').setFontStyle('italic').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E10').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$G:$G, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('F10').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$H:$H, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('G10').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('H10').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$J:$J, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('I10').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$K:$K, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('J10').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$L:$L, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('K10').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$M:$M, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('L10').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$N:$N, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('M10').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$O:$O, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('N10').setFormula('=(G10 - G11)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('A10:N10').setBackground('#F0FFF4');

  // Row 11: Benchmark Row
  sheet.getRange('A11').setFormula('="Benchmark: " & $J$2 & " Total Return"').setFontStyle('italic').setHorizontalAlignment('left').setVerticalAlignment('middle');
  sheet.getRange('B11').setFormula('=IF($J$2="MSCI World", "All World", "S&P 500")').setFontStyle('italic').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C11').setFormula('=$F$2').setFontStyle('italic').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D11').setValue('—').setFontStyle('italic').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$G:$G, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('F11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$H:$H, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('G11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('H11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$J:$J, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('I11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$K:$K, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('J11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$L:$L, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('K11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$M:$M, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('L11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$N:$N, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('M11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$O:$O, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('N11').setValue('—').setFontStyle('italic').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('A11:N11').setBackground('#EDF2F7').setFontColor('#4A5568');

  // Row 12: Net Advantage / Delta Row
  sheet.getRange('A12').setFormula('="Net Advantage (Strategy vs " & $J$2 & ")"').setFontWeight('bold').setHorizontalAlignment('left').setVerticalAlignment('middle');
  sheet.getRange('B12:D12').setValue('—').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E12').setFormula('=(E10 - E11)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('F12').setFormula('=(F10 - F11)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('G12').setFormula('=(G10 - G11)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('H12').setFormula('=(H10 - H11)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('I12').setFormula('=(I10 - I11)').setNumberFormat('[Color10]+$#,##0.00;[Red]-$#,##0.00;$0.00').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('J12').setFormula('=(J10 - J11)').setNumberFormat('[Color10]+$#,##0.00;[Red]-$#,##0.00;$0.00').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('K12').setFormula('=(K10 - K11)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('L12').setFormula('=(L10 - L11)').setNumberFormat('+$#,##0.00;-$#,##0.00;$0.00').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('M12').setFormula('=(M10 - M11)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('N12').setFormula('=(G10 - G11)').setNumberFormat('[Color10]+0.00%;[Red]-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('A12:N12').setBackground('#FEFCBF');

  // Borders for table (Rows 9-12)
  sheet.getRange(9, 1, 4, tableHeaders.length).setBorder(true, true, true, true, true, true, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // 5. Key Metrics Glossary & Explanations (Rows 14-18, directly below table)
  sheet.getRange('A14:N14').merge()
       .setValue('KEY METRIC DEFINITIONS & GLOSSARY')
       .setBackground('#EDF2F7')
       .setFontColor('#2D3748')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle');

  var explanationsGrid = [
    [
      ['Annual Return (CAGR):', 'Smoothed annual percentage portfolio grew compounded steadily.'],
      ['Annual Alpha:', 'Additional annual compound return earned above benchmark index.']
    ],
    [
      ['Total Return (Cumulative):', 'Unannualized percentage wealth gain over the entire holding horizon.'],
      ['Annual Tax Drag:', 'Annual return lost to taxes (Pre-Tax CAGR minus Post-Liq CAGR).']
    ],
    [
      ['Post-Liquidation Return:', 'True net annual return assuming full final portfolio sale and tax settlement.'],
      ['Max Drawdown:', 'Worst peak-to-trough percentage decline before a new high was reached.']
    ],
    [
      ['Ending Wealth:', 'Final liquidated portfolio equity value scaled to active Seed Capital.'],
      ['Dividends & Cash Pooling:', 'Split-adjusted discrete cash collections reinvested at rebalance dates.']
    ]
  ];

  for (var eg = 0; eg < explanationsGrid.length; eg++) {
    var gr = 15 + eg;
    var rowItem = explanationsGrid[eg];
    // Left definition (Cols A-B label, Cols C-G definition)
    sheet.getRange('A' + gr + ':B' + gr).merge()
         .setValue(rowItem[0][0])
         .setFontWeight('bold')
         .setFontSize(9)
         .setFontColor('#4A5568')
         .setHorizontalAlignment('right')
         .setVerticalAlignment('middle');
    sheet.getRange('C' + gr + ':G' + gr).merge()
         .setValue(rowItem[0][1])
         .setFontSize(9)
         .setFontColor('#718096')
         .setHorizontalAlignment('left')
         .setVerticalAlignment('middle');
    // Right definition (Cols H-I label, Cols J-N definition)
    sheet.getRange('H' + gr + ':I' + gr).merge()
         .setValue(rowItem[1][0])
         .setFontWeight('bold')
         .setFontSize(9)
         .setFontColor('#4A5568')
         .setHorizontalAlignment('right')
         .setVerticalAlignment('middle');
    sheet.getRange('J' + gr + ':N' + gr).merge()
         .setValue(rowItem[1][1])
         .setFontSize(9)
         .setFontColor('#718096')
         .setHorizontalAlignment('left')
         .setVerticalAlignment('middle');
    sheet.setRowHeight(gr, 22);
  }
  sheet.getRange(14, 1, 5, 14).setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // 6. Methodology Note Callout Card (Rows 20-25)
  sheet.getRange('A20:N20').merge()
       .setValue('METHODOLOGY NOTE — REBALANCING, TAXES & DIVIDENDS')
       .setBackground('#2D3748')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle');

  var methodBullets = [
    '• Rebalancing Frequency: Supports Annual (year-end factsheet weights) and Quarterly (Q1-Q3 dynamic price drift, Q4 factsheet re-anchored) rebalancing.',
    '• Discrete Dividends: Historical dividends are collected discrete-quarterly or discrete-annually and credited prior to rebalancing.',
    '• Tax Settlement: Dividend and realized capital gains taxes are settled at the selected marginal tax rate, with capital loss carryforwards applied.',
    '• Self-Financing Rebalancing: Net dividend income is reinvested into target holdings alongside rebalancing trade proceeds without margin borrowing (cash >= 0).',
    '• Benchmark Alignment & Universes: S&P 500 represents domestic mega-caps; All World includes global market cap leaders accessible via US markets.'
  ];

  for (var mb = 0; mb < methodBullets.length; mb++) {
    var mrRow = 21 + mb;
    sheet.getRange('A' + mrRow + ':N' + mrRow).merge()
         .setValue(methodBullets[mb])
         .setFontSize(9)
         .setFontColor('#4A5568')
         .setHorizontalAlignment('left')
         .setVerticalAlignment('middle')
         .setWrap(true);
    sheet.setRowHeight(mrRow, 20);
  }

  sheet.getRange(20, 1, 6, 14).setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange('A21:N25').setBackground('#F7FAFC');

  // Explicit, proportional column widths (14 columns)
  var colWidths = [120, 80, 65, 75, 95, 95, 95, 95, 115, 105, 95, 95, 90, 110];
  for (var c = 0; c < colWidths.length; c++) {
    sheet.setColumnWidth(c + 1, colWidths[c]);
  }

  // Explicit row heights for single-screen view without vertical scrolling
  sheet.setRowHeight(1, 40);
  sheet.setRowHeight(2, 32);
  sheet.setRowHeight(3, 8);
  sheet.setRowHeight(4, 22);
  sheet.setRowHeight(5, 32);
  sheet.setRowHeight(6, 20);
  sheet.setRowHeight(7, 10);
  sheet.setRowHeight(8, 30);
  sheet.setRowHeight(9, 36);
  sheet.setRowHeight(10, 24);
  sheet.setRowHeight(11, 24);
  sheet.setRowHeight(12, 24);
  sheet.setRowHeight(13, 10);
  sheet.setRowHeight(14, 24);
  sheet.setRowHeight(19, 10);
  sheet.setRowHeight(20, 24);

  // Freeze top 2 rows (Banner & Controls) for clean navigation
  sheet.setFrozenRows(2);
}

// ==========================================
// Tab 2: Performance & Tradeoffs (Charts & Regimes)
// ==========================================
function buildPerformanceAndTradeoffsSheet(ss) {
  var sheet = getOrCreateSheet(ss, 'Performance & Tradeoffs');
  sheet.setHiddenGridlines(false);

  // 1. Banner Header
  sheet.getRange('A1:L1').merge()
       .setValue('S&P 500 TOP N STRATEGY - HISTORICAL CHARTS & TRADEOFF ANALYSIS')
       .setBackground('#1B365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(14)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(1, 40);

  // 2. Subtitle Description
  sheet.getRange('A2:L2').merge()
       .setFormula('="Visualizing 30-year compounded wealth trajectories (" & TEXT(\'Executive Summary\'!$N$2, "$#,##0") & " initial basis), peak-to-trough drawdowns, and regime attribution (1994–2024)."')
       .setFontStyle('italic')
       .setFontColor('#4A5568')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(2, 24);

  // 3. Section Title: Market Regime Attribution
  sheet.getRange('A4:H4').merge()
       .setValue('HISTORICAL MARKET REGIME ATTRIBUTION (4 ERAS)')
       .setBackground('#2C5282')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(11)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(4, 28);

  // 4. Market Regime Table Headers
  sheet.getRange(5, 1, 1, ERA_HEADERS.length).setValues([ERA_HEADERS])
       .setBackground('#2B6CB0')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(5, 26);

  // 5. Market Regime Data Rows
  sheet.getRange(6, 1, ERA_DATA.length, ERA_HEADERS.length).setValues(ERA_DATA);
  for (var er = 0; er < ERA_DATA.length; er++) {
    var rowNum = 6 + er;
    var bg = (er === ERA_DATA.length - 1) ? '#EDF2F7' : ((er % 2 === 0) ? '#FFFFFF' : '#F7FAFC');
    sheet.getRange(rowNum, 1, 1, ERA_HEADERS.length).setBackground(bg);
    sheet.setRowHeight(rowNum, 22);
  }

  // Regime Table Formatting
  sheet.getRange(6, 1, ERA_DATA.length, 1).setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange(6, 2, ERA_DATA.length, 1).setVerticalAlignment('middle');
  sheet.getRange(6, 3, ERA_DATA.length, 4).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(6, 7, ERA_DATA.length, 1).setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(6, 8, ERA_DATA.length, 1).setNumberFormat('0.0%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(5, 1, ERA_DATA.length + 1, ERA_HEADERS.length).setBorder(true, true, true, true, true, true, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange(6 + ERA_DATA.length - 1, 1, 1, ERA_HEADERS.length).setFontWeight('bold');

  // Spacer
  sheet.setRowHeight(11, 12);

  for (var cr = 12; cr <= 29; cr++) {
    sheet.setRowHeight(cr, 20);
  }
  sheet.setRowHeight(30, 14);

  // 6. Section Titles for Time Series Data
  sheet.getRange('A31:E31').merge()
       .setFormula('="30-YEAR WEALTH ACCUMULATION DATA (" & TEXT(\'Executive Summary\'!$N$2, "$#,##0") & " BASIS)"')
       .setBackground('#2C5282')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');

  sheet.getRange('G31:K31').merge()
       .setValue('HISTORICAL DRAWDOWN FROM PEAK DATA')
       .setBackground('#2C5282')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(31, 26);

  // Table Headers (Row 32)
  sheet.getRange(32, 1, 1, TRAJECTORY_HEADERS.length).setValues([TRAJECTORY_HEADERS])
       .setBackground('#4A5568')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');

  sheet.getRange(32, 7, 1, DRAWDOWN_HEADERS.length).setValues([DRAWDOWN_HEADERS])
       .setBackground('#4A5568')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(32, 24);

  // Trajectory & Drawdown Data (Rows 33 to 63, length 31)
  var trajRows = [];
  for (var tr = 0; tr < TRAJECTORY_DATA.length; tr++) {
    var trow = [TRAJECTORY_DATA[tr][0]];
    for (var tc = 1; tc <= 4; tc++) {
      trow.push('=' + TRAJECTORY_DATA[tr][tc] + ' * ' + SCALE_EXPR);
    }
    trajRows.push(trow);
  }
  sheet.getRange(33, 1, trajRows.length, TRAJECTORY_HEADERS.length).setValues(trajRows);
  sheet.getRange(33, 7, DRAWDOWN_DATA.length, DRAWDOWN_HEADERS.length).setValues(DRAWDOWN_DATA);

  // Formatting Trajectory Table
  sheet.getRange(33, 1, TRAJECTORY_DATA.length, 1).setNumberFormat('####').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange(33, 2, TRAJECTORY_DATA.length, 4).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(32, 1, TRAJECTORY_DATA.length + 1, TRAJECTORY_HEADERS.length).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);

  // Formatting Drawdown Table
  sheet.getRange(33, 7, DRAWDOWN_DATA.length, 1).setNumberFormat('####').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange(33, 8, DRAWDOWN_DATA.length, 4).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(32, 7, DRAWDOWN_DATA.length + 1, DRAWDOWN_HEADERS.length).setBorder(true, true, true, true, true, true, '#E2E8F0', SpreadsheetApp.BorderStyle.SOLID);

  for (var tr = 0; tr < TRAJECTORY_DATA.length; tr++) {
    var rowN = 33 + tr;
    var bgRow = (tr % 2 === 0) ? '#FFFFFF' : '#F7FAFC';
    sheet.getRange(rowN, 1, 1, TRAJECTORY_HEADERS.length).setBackground(bgRow);
    sheet.getRange(rowN, 7, 1, DRAWDOWN_HEADERS.length).setBackground(bgRow);
    sheet.setRowHeight(rowN, 20);
  }

  // Set explicit column widths
  var pColWidths = [75, 110, 110, 110, 115, 30, 75, 105, 105, 105, 105, 30];
  for (var pw = 0; pw < pColWidths.length; pw++) {
    sheet.setColumnWidth(pw + 1, pColWidths[pw]);
  }

  // Flush all cell values and formats to spreadsheet before creating charts
  SpreadsheetApp.flush();

  // 7. Embedded Native Charts (Rows 12 to 29)
  // Chart 1: Growth of Seed Capital Line Chart (Logarithmic Scale)
  var growthRange = sheet.getRange(32, 1, TRAJECTORY_DATA.length + 1, TRAJECTORY_HEADERS.length);
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
    .setOption('width', 580)
    .setOption('height', 360)
    .setPosition(12, 1, 0, 0)
    .build();
  sheet.insertChart(growthChart);

  // Chart 2: Historical Drawdowns from Peak Line Chart
  var ddRange = sheet.getRange(32, 7, DRAWDOWN_DATA.length + 1, DRAWDOWN_HEADERS.length);
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
    .setOption('width', 580)
    .setOption('height', 360)
    .setPosition(12, 7, 0, 0)
    .build();
  sheet.insertChart(ddChart);
}

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
  sheet.getRange('D1').setFormula('="Compounded Growth (" & TEXT(\'Executive Summary\'!$N$2, "$#,##0") & " Invested)"');

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
  var taxRateVal = sheet.getRange('L2').getValue();
  var taxRateStr = (typeof taxRateVal === 'number') ? (taxRateVal * 100).toFixed(1) + '%' : String(taxRateVal);
  var univVal = sheet.getRange('B2').getValue();
  var stratVal = sheet.getRange('D2').getValue();
  var horizVal = sheet.getRange('F2').getValue();
  var seedVal = sheet.getRange('N2').getValue();
  var seedStr = (typeof seedVal === 'number') ? '$' + seedVal.toLocaleString() : String(seedVal);
  SpreadsheetApp.flush();
  ss.toast('Spotlight: ' + univVal + ' ' + stratVal + ' (' + horizVal + '), Tax: ' + taxRateStr + ', Seed: ' + seedStr, 'Recalculation Complete', 4);
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
