// ============================================================================
// COORDINATE CONTRACT WITH 03_performance_tradeoffs.js:
// Cols 1-18 (A-R):   Scenario Matrix
// Cols 20-25 (T-Y):  Trajectory Matrix (FILTER referenced in Tab 2, A43)
// Cols 27-32 (AA-AF): Drawdown Matrix  (FILTER referenced in Tab 2, G43)
// Cols 34-42 (AH-AP): Era Matrix       (FILTER referenced in Tab 2, A6)
// ============================================================================
// ==========================================
// Tab 1: Scenario Data (Lookup Engine)
// ==========================================
function buildScenarioDataSheet(ss) {
  var sheet = getOrCreateSheet(ss, 'Scenario Data');
  sheet.setHiddenGridlines(false);

  var decoratedData = [];
  for (var i = 0; i < SCENARIO_DATA.length; i++) {
    var r = SCENARIO_DATA[i].slice();
    r[11] = '=' + r[11] + ' * ' + SCALE_EXPR;
    r[12] = '=' + r[12] + ' * ' + SCALE_EXPR;
    r[14] = '=' + r[14] + ' * ' + SCALE_EXPR;
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

  // Number Formatting (18 columns)
  if (SCENARIO_DATA.length > 0) {
    sheet.getRange(2, 1, SCENARIO_DATA.length, 1).setHorizontalAlignment('left');
    sheet.getRange(2, 2, SCENARIO_DATA.length, 1).setNumberFormat('0.0%').setHorizontalAlignment('center');
    sheet.getRange(2, 3, SCENARIO_DATA.length, 2).setHorizontalAlignment('center');
    sheet.getRange(2, 5, SCENARIO_DATA.length, 1).setHorizontalAlignment('left');
    sheet.getRange(2, 6, SCENARIO_DATA.length, 1).setHorizontalAlignment('center');
    sheet.getRange(2, 7, SCENARIO_DATA.length, 1).setHorizontalAlignment('center');
    sheet.getRange(2, 8, SCENARIO_DATA.length, 4).setNumberFormat('0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 12, SCENARIO_DATA.length, 2).setNumberFormat('$#,##0.00').setHorizontalAlignment('right');
    sheet.getRange(2, 14, SCENARIO_DATA.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 15, SCENARIO_DATA.length, 1).setNumberFormat('$#,##0.00').setHorizontalAlignment('right');
    sheet.getRange(2, 16, SCENARIO_DATA.length, 1).setNumberFormat('0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 17, SCENARIO_DATA.length, 1).setNumberFormat('+0.00%;-0.00%;0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 18, SCENARIO_DATA.length, 1).setHorizontalAlignment('center');
  }

  sheet.autoResizeColumns(1, SCENARIO_HEADERS.length);

  // Trajectory Matrix (Cols T to Y, Col 20 to 25)
  if (typeof TRAJECTORY_MATRIX !== 'undefined' && TRAJECTORY_MATRIX.length > 0) {
    var decoratedTraj = [];
    for (var ti = 0; ti < TRAJECTORY_MATRIX.length; ti++) {
      var trow = TRAJECTORY_MATRIX[ti].slice();
      // Cols 2, 3, 4, 5 are dollar series: Top 3, Top 5, Top 10, Benchmark
      trow[2] = '=' + trow[2] + ' * ' + SCALE_EXPR;
      trow[3] = '=' + trow[3] + ' * ' + SCALE_EXPR;
      trow[4] = '=' + trow[4] + ' * ' + SCALE_EXPR;
      trow[5] = '=' + trow[5] + ' * ' + SCALE_EXPR;
      decoratedTraj.push(trow);
    }
    var trajAllRows = [TRAJECTORY_MATRIX_HEADERS].concat(decoratedTraj);
    sheet.getRange(1, 20, trajAllRows.length, TRAJECTORY_MATRIX_HEADERS.length).setValues(trajAllRows);
    sheet.getRange(1, 20, 1, TRAJECTORY_MATRIX_HEADERS.length)
         .setBackground('#2C5282').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
    sheet.getRange(2, 20, TRAJECTORY_MATRIX.length, 1).setHorizontalAlignment('left');
    sheet.getRange(2, 21, TRAJECTORY_MATRIX.length, 1).setNumberFormat('####').setHorizontalAlignment('center');
    sheet.getRange(2, 22, TRAJECTORY_MATRIX.length, 4).setNumberFormat('$#,##0.00').setHorizontalAlignment('right');
  }

  // Drawdown Matrix (Cols AA to AF, Col 27 to 32)
  if (typeof DRAWDOWN_MATRIX !== 'undefined' && DRAWDOWN_MATRIX.length > 0) {
    var ddAllRows = [DRAWDOWN_MATRIX_HEADERS].concat(DRAWDOWN_MATRIX);
    sheet.getRange(1, 27, ddAllRows.length, DRAWDOWN_MATRIX_HEADERS.length).setValues(ddAllRows);
    sheet.getRange(1, 27, 1, DRAWDOWN_MATRIX_HEADERS.length)
         .setBackground('#2C5282').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
    sheet.getRange(2, 27, DRAWDOWN_MATRIX.length, 1).setHorizontalAlignment('left');
    sheet.getRange(2, 28, DRAWDOWN_MATRIX.length, 1).setNumberFormat('####').setHorizontalAlignment('center');
    sheet.getRange(2, 29, DRAWDOWN_MATRIX.length, 4).setNumberFormat('0.00%').setHorizontalAlignment('right');
  }

  // Era Matrix (Cols AH to AP, Col 34 to 42)
  if (typeof ERA_MATRIX !== 'undefined' && ERA_MATRIX.length > 0) {
    var eraAllRows = [ERA_MATRIX_HEADERS].concat(ERA_MATRIX);
    sheet.getRange(1, 34, eraAllRows.length, ERA_MATRIX_HEADERS.length).setValues(eraAllRows);
    sheet.getRange(1, 34, 1, ERA_MATRIX_HEADERS.length)
         .setBackground('#2C5282').setFontColor('#FFFFFF').setFontWeight('bold').setHorizontalAlignment('center');
    sheet.getRange(2, 34, ERA_MATRIX.length, 1).setHorizontalAlignment('left');
    sheet.getRange(2, 35, ERA_MATRIX.length, 1).setHorizontalAlignment('center');
    sheet.getRange(2, 36, ERA_MATRIX.length, 1).setHorizontalAlignment('left');
    sheet.getRange(2, 37, ERA_MATRIX.length, 4).setNumberFormat('0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 41, ERA_MATRIX.length, 1).setNumberFormat('+0.00%;-0.00%;0.00%').setHorizontalAlignment('right');
    sheet.getRange(2, 42, ERA_MATRIX.length, 1).setNumberFormat('0.0%').setHorizontalAlignment('right');
  }

  sheet.setFrozenRows(1);
}

