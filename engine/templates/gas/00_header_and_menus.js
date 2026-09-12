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
var SCALE_EXPR = "(IF(AND(ISNUMBER('Executive Summary'!$H$3), 'Executive Summary'!$H$3 > 0), 'Executive Summary'!$H$3, " + BASE_INITIAL_CAPITAL + ") / " + BASE_INITIAL_CAPITAL + ")";

var SCENARIO_HEADERS = [
  "LookupKey", "TaxRate", "Universe", "Horizon", "Strategy", "Weighting", "Frequency", "PreTaxCAGR",
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

var ERA_MATRIX_HEADERS = [
  "LookupKey", "Market Regime Era", "Historical Context / Regime", "Top 3 CAGR",
  "Top 5 CAGR", "Top 10 CAGR", "Benchmark CAGR", "Top 10 Alpha", "Top 10 Win Rate"
];
var ERA_MATRIX = /*__ERA_MATRIX__*/[];

var TRAJECTORY_MATRIX_HEADERS = ["LookupKey", "Year", "Top 3 ($)", "Top 5 ($)", "Top 10 ($)", "Benchmark ($)"];
var TRAJECTORY_MATRIX = /*__TRAJECTORY_MATRIX__*/[];

var DRAWDOWN_MATRIX_HEADERS = ["LookupKey", "Year", "Top 3 Drawdown", "Top 5 Drawdown", "Top 10 Drawdown", "Benchmark Drawdown"];
var DRAWDOWN_MATRIX = /*__DRAWDOWN_MATRIX__*/[];

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

