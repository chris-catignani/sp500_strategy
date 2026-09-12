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
       .setValue('S&P 500 & ALL-WORLD TOP N STRATEGY - EXECUTIVE DASHBOARD')
       .setBackground('#1B365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(14)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle')
       .setWrapStrategy(SpreadsheetApp.WrapStrategy.OVERFLOW);

  // 2. Interactive Parameter Dropdowns in Row 2
  // Control 1: Tax Rate (Cols A-B)
  sheet.getRange('A2').setValue('Tax Rate:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var b2 = sheet.getRange('B2');
  b2.setValue(0.30)
    .setNumberFormat('0.0%')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  var taxRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['0.0%', '15.0%', '20.0%', '30.0%', '37.0%'], true)
    .setAllowInvalid(false)
    .build();
  b2.setDataValidation(taxRule);

  // Control 2: Universe (Cols C-D)
  sheet.getRange('C2').setValue('Universe:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var d2 = sheet.getRange('D2');
  d2.setValue('All')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  var univRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['All', 'S&P 500 Only', 'All World Only'], true)
    .setAllowInvalid(false)
    .build();
  d2.setDataValidation(univRule);

  // Control 3: Strategy (Cols E-F)
  sheet.getRange('E2').setValue('Strategy:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var f2 = sheet.getRange('F2');
  f2.setValue('All')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  var stratRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['All', 'Top 3', 'Top 5', 'Top 10'], true)
    .setAllowInvalid(false)
    .build();
  f2.setDataValidation(stratRule);

  // Control 4: Horizon (Cols G-H)
  sheet.getRange('G2').setValue('Horizon:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var h2 = sheet.getRange('H2');
  h2.setValue('All')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  var horizRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['All', '10y', '20y', '30y'], true)
    .setAllowInvalid(false)
    .build();
  h2.setDataValidation(horizRule);

  // Control 5: Compare Index (Cols I-J)
  sheet.getRange('I2').setValue('Compare Index:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var j2 = sheet.getRange('J2');
  j2.setValue('Both')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  var indexRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['None', 'S&P 500', 'MSCI World', 'Both'], true)
    .setAllowInvalid(false)
    .build();
  j2.setDataValidation(indexRule);

  // Control 6: Rebalance Frequency (Cols K-L)
  sheet.getRange('K2').setValue('Rebalance:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var l2 = sheet.getRange('L2');
  l2.setValue('All')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  var freqRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['All', 'Annual Only', 'Quarterly Only'], true)
    .setAllowInvalid(false)
    .build();
  l2.setDataValidation(freqRule);

  // Control 7: Seed Capital (Cols M-N)
  sheet.getRange('M2').setValue('Seed Capital:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var n2 = sheet.getRange('N2');
  n2.setValue(BASE_INITIAL_CAPITAL)
    .setNumberFormat('$#,##0')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  var seedRule = SpreadsheetApp.newDataValidation()
    .requireNumberGreaterThan(0)
    .setAllowInvalid(false)
    .setHelpText('Please enter a positive seed investment amount.')
    .build();
  n2.setDataValidation(seedRule);

  // 3. KPI Summary Scorecards (Rows 4-6)
  // Decoupled formulas query 'Scenario Data' directly using INDEX/MATCH for robust filter resilience
  // Card 1: Top 5 Final Wealth (30y) (Cols A-B)
  sheet.getRange('A4:B4').merge().setValue('Top 5 Final Wealth (30y)').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A5:B5').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$K:$K, MATCH("30y_" & IF($D$2="All World Only","All World","S&P 500") & "_Top 5_" & IF($L$2="Quarterly Only","Quarterly","Annual") & "_" & TEXT($B$2, "0.0%"), \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#22543D').setNumberFormat('$#,##0.00').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A6:B6').merge().setFormula('="After all taxes (" & TEXT($N$2, "$#,##0") & " start)"').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A4:B6').setBackground('#E6FFFA').setBorder(true, true, true, true, false, false, '#B2F5EA', SpreadsheetApp.BorderStyle.SOLID);

  // Card 2: Benchmark Wealth (30y) (Cols C-E)
  sheet.getRange('C4:E4').merge().setFormula('=IF($D$2="All World Only", "MSCI World Wealth (30y)", "S&P 500 Wealth (30y)")').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C5:E5').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$K:$K, MATCH("30y_" & IF($D$2="All World Only","All World_MSCI World","S&P 500_S&P 500") & "_" & IF($L$2="Quarterly Only","Quarterly","Annual") & "_" & TEXT($B$2, "0.0%"), \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#4A5568').setNumberFormat('$#,##0.00').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C6:E6').merge().setValue('Passive buy & hold').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C4:E6').setBackground('#EDF2F7').setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // Card 3: Top 5 Annual Return (30y) (Cols F-G)
  sheet.getRange('F4:G4').merge().setValue('Top 5 Annual Return (30y)').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('F5:G5').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH("30y_" & IF($D$2="All World Only","All World","S&P 500") & "_Top 5_" & IF($L$2="Quarterly Only","Quarterly","Annual") & "_" & TEXT($B$2, "0.0%"), \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#1B365D').setNumberFormat('0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('F6:G6').merge().setValue('Net post-liquidation CAGR').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('F4:G6').setBackground('#EBF8FF').setBorder(true, true, true, true, false, false, '#BEE3F8', SpreadsheetApp.BorderStyle.SOLID);

  // Card 4: 30-Year Excess Return (Cols H-J)
  sheet.getRange('H4:J4').merge().setValue('30-Year Excess Return').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('H5:J5').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$P:$P, MATCH("30y_" & IF($D$2="All World Only","All World","S&P 500") & "_Top 5_" & IF($L$2="Quarterly Only","Quarterly","Annual") & "_" & TEXT($B$2, "0.0%"), \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#22543D').setNumberFormat('+0.00%;-0.00%;0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('H6:J6').merge().setValue('Annual Alpha vs S&P 500').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('H4:J6').setBackground('#F0FFF4').setBorder(true, true, true, true, false, false, '#C6F6D5', SpreadsheetApp.BorderStyle.SOLID);

  // Card 5: 30-Year Tax Drag (Cols K-N)
  sheet.getRange('K4:N4').merge().setValue('30-Year Tax Drag').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('K5:N5').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$O:$O, MATCH("30y_" & IF($D$2="All World Only","All World","S&P 500") & "_Top 5_" & IF($L$2="Quarterly Only","Quarterly","Annual") & "_" & TEXT($B$2, "0.0%"), \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#9B2C2C').setNumberFormat('0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('K6:N6').merge().setValue('Annual return lost to taxes').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('K4:N6').setBackground('#FFF5F5').setBorder(true, true, true, true, false, false, '#FED7D7', SpreadsheetApp.BorderStyle.SOLID);

  // 4. Multi-Horizon Strategy Comparison Table
  // Row 8: Title
  sheet.getRange('A8:N8').merge()
       .setValue('MULTI-HORIZON PERFORMANCE & TAX COMPARISON (10Y, 20Y, 30Y)')
       .setBackground('#1B365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(11)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');

  // Row 9: Table Header (14 columns matching 'Scenario Data'!$C:$P)
  var tableHeaders = [
    'Universe', 'Horizon', 'Strategy', 'Frequency', 'Annual Return (Pre-Tax)', 'Annual Return (After-Tax)', 'Annual Return (Post-Liq)',
    'Total Return (Cumulative)', 'Ending Wealth', 'Total Dividends Received',
    'Max Drawdown (Worst Drop)', 'Total Taxes Paid', 'Annual Tax Drag', 'Excess vs S&P 500 (Alpha)'
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

  // Row 10: Dynamic Filter Formula spilling down Rows 10:77 (guarded by non-empty $A$2:$A to prevent spill on 0.0% tax rate)
  var filterFormula = '=IFNA(FILTER(\'Scenario Data\'!$C$2:$P, (\'Scenario Data\'!$A$2:$A <> "") * (ROUND(\'Scenario Data\'!$B$2:$B, 4) = ROUND($B$2, 4)) * (($H$2 = "All") + (\'Scenario Data\'!$D$2:$D = $H$2)) * (($L$2 = "All") + (\'Scenario Data\'!$F$2:$F = SUBSTITUTE($L$2, " Only", ""))) * (((\'Scenario Data\'!$Q$2:$Q = "Strategy") * (($D$2 = "All") + (\'Scenario Data\'!$C$2:$C = SUBSTITUTE($D$2, " Only", ""))) * (($F$2 = "All") + (\'Scenario Data\'!$E$2:$E = $F$2))) + ((\'Scenario Data\'!$Q$2:$Q = "Index") * ((($J$2 = "Both") * 1) + ((\'Scenario Data\'!$E$2:$E = $J$2) * 1))))), "No matching records found")';
  sheet.getRange('A10').setFormula(filterFormula);

  // Pre-formatting comparison table range (Rows 10 to 77, unmerged for spill protection)
  sheet.getRange(10, 1, 68, 1).setHorizontalAlignment('center').setFontWeight('bold').setVerticalAlignment('middle');
  sheet.getRange(10, 2, 68, 1).setHorizontalAlignment('center').setFontWeight('bold').setVerticalAlignment('middle');
  sheet.getRange(10, 3, 68, 1).setFontWeight('bold').setVerticalAlignment('middle');
  sheet.getRange(10, 4, 68, 1).setFontStyle('italic').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange(10, 5, 68, 3).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 8, 68, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 9, 68, 2).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 11, 68, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 12, 68, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 13, 68, 1).setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange(10, 14, 68, 1).setNumberFormat('+0.00%;-0.00%;0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');

  // Alternating background colors and benchmark tint via conditional formatting rules
  var cfRange = sheet.getRange('A10:N77');
  var ruleIndex = SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied('=AND($A10<>"", $A10<>"No matching records found", OR($C10="S&P 500", $C10="MSCI World"))')
    .setBackground('#EDF2F7')
    .setFontColor('#2D3748')
    .setItalic(true)
    .setRanges([cfRange])
    .build();
  var ruleEven = SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied('=AND($A10<>"", $A10<>"No matching records found", MOD(ROW(), 2)=0)')
    .setBackground('#F7FAFC')
    .setRanges([cfRange])
    .build();
  var ruleOdd = SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied('=AND($A10<>"", $A10<>"No matching records found", MOD(ROW(), 2)=1)')
    .setBackground('#FFFFFF')
    .setRanges([cfRange])
    .build();
  sheet.setConditionalFormatRules([ruleIndex, ruleEven, ruleOdd]);

  // Borders
  sheet.getRange(9, 1, 69, tableHeaders.length).setBorder(true, true, true, true, true, true, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // Explicit, proportional column widths (14 columns)
  var colWidths = [85, 70, 95, 80, 100, 100, 100, 100, 110, 105, 100, 95, 95, 95];
  for (var c = 0; c < colWidths.length; c++) {
    sheet.setColumnWidth(c + 1, colWidths[c]);
  }

  // Explicit row heights for polished vertical rhythm
  sheet.setRowHeight(1, 40);
  sheet.setRowHeight(2, 32);
  sheet.setRowHeight(3, 10);
  sheet.setRowHeight(4, 22);
  sheet.setRowHeight(5, 32);
  sheet.setRowHeight(6, 20);
  sheet.setRowHeight(7, 14);
  sheet.setRowHeight(8, 30);
  sheet.setRowHeight(9, 36);
  for (var dr = 10; dr <= 77; dr++) {
    sheet.setRowHeight(dr, 24);
  }

  // 5. Key Metrics Glossary & Explanations (Rows 80-86, leaving Rows 10:77 completely unmerged)
  sheet.setRowHeight(78, 14);
  sheet.setRowHeight(79, 10);
  sheet.getRange('A80:N80').merge()
       .setValue('KEY METRIC DEFINITIONS & GLOSSARY')
       .setBackground('#EDF2F7')
       .setFontColor('#2D3748')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(80, 24);

  var explanations = [
    ['Annual Return (CAGR):', 'Compound Annual Growth Rate — the smoothed annual percentage your money grew every year compounded steadily.'],
    ['Total Return (Cumulative):', 'The total unannualized percentage gain over the entire period (e.g. +795.6% means $10k turned into $89.5k).'],
    ['Post-Liquidation Return:', 'True net annual return assuming all remaining stock holdings are sold at the end and all final taxes paid.'],
    ['Annual Tax Drag:', 'Annual percentage of return lost to taxes. Calculated as Pre-Tax Annual Return minus Post-Liquidation Annual Return.'],
    ['Excess vs S&P 500 (Alpha):', 'Additional annual return earned above the S&P 500 benchmark (+5.81% means beating the market by 5.81%/yr).'],
    ['Max Drawdown:', 'Worst percentage drop from peak to trough during market downturns before a new high was reached.']
  ];

  for (var e = 0; e < explanations.length; e++) {
    var r = 81 + e;
    sheet.getRange('A' + r + ':B' + r).merge()
         .setValue(explanations[e][0])
         .setFontWeight('bold')
         .setFontSize(9)
         .setFontColor('#4A5568')
         .setHorizontalAlignment('right')
         .setVerticalAlignment('middle');
    sheet.getRange('C' + r + ':N' + r).merge()
         .setValue(explanations[e][1])
         .setFontSize(9)
         .setFontColor('#718096')
         .setHorizontalAlignment('left')
         .setVerticalAlignment('middle');
    sheet.setRowHeight(r, 20);
  }

  // 6. Methodology Note Callout Card (Rows 89-95)
  sheet.setRowHeight(87, 14);
  sheet.setRowHeight(88, 10);
  sheet.getRange('A89:N89').merge()
       .setValue('METHODOLOGY NOTE — DIVIDEND TIMING & MULTI-UNIVERSE SELECTION')
       .setBackground('#2D3748')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(10)
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle');
  sheet.setRowHeight(89, 24);

  var methodNote = '• Rebalancing Frequency: Supports Annual (year-end factsheet weights) and Quarterly (Q1-Q3 dynamic price drift, Q4 factsheet re-anchored) rebalancing.\n' +
                   '• Discrete Dividends: Historical dividends are collected discrete-quarterly or discrete-annually and credited prior to rebalancing.\n' +
                   '• Tax Settlement: Dividend and realized capital gains taxes are settled at the selected marginal tax rate, with capital loss carryforwards applied.\n' +
                   '• Self-Financing Rebalancing: Net dividend income is reinvested into target holdings alongside rebalancing trade proceeds without margin borrowing (cash >= 0).\n' +
                   '• Post-Liquidation Terminal Wealth: Terminal equity reflects a full simulated liquidation of all portfolio holdings with final capital gains taxes paid.\n' +
                   '• Benchmark Alignment: S&P 500 total return benchmark reflects split- and dividend-adjusted performance over identical holding periods.\n' +
                   '• Multi-Universe Scope: S&P 500 represents domestic mega-caps; All World includes global market cap leaders accessible via US markets (ADRs / direct listings).';

  sheet.getRange('A90:N95').merge()
       .setValue(methodNote)
       .setFontSize(9)
       .setFontColor('#4A5568')
       .setHorizontalAlignment('left')
       .setVerticalAlignment('middle')
       .setWrap(true);

  sheet.getRange('A89:N95').setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange('A90:N95').setBackground('#F7FAFC');
  for (var mr = 90; mr <= 95; mr++) {
    sheet.setRowHeight(mr, 18);
  }

  sheet.setFrozenRows(9);
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
  var taxRateVal = sheet.getRange('B2').getValue();
  var taxRateStr = (typeof taxRateVal === 'number') ? (taxRateVal * 100).toFixed(1) + '%' : String(taxRateVal);
  var seedVal = sheet.getRange('N2').getValue();
  var seedStr = (typeof seedVal === 'number') ? '$' + seedVal.toLocaleString() : String(seedVal);
  SpreadsheetApp.flush();
  ss.toast('Dashboard updated for Tax Rate: ' + taxRateStr + ', Seed Capital: ' + seedStr, 'Recalculation Complete', 3);
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
    var charts = sheet.getCharts();
    for (var i = 0; i < charts.length; i++) {
      sheet.removeChart(charts[i]);
    }
  } else {
    sheet = ss.insertSheet(name);
  }
  return sheet;
}
