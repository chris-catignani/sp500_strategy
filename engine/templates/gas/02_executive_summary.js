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

  // 2. Interactive Parameter Dropdowns in Rows 2 & 3 (8 Controls across 14 columns)
  // Clear any existing data validation rules from previous builds
  sheet.getRange('A2:N3').clearDataValidations();

  // --- ROW 2: Portfolio Target Controls ---
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

  // Control 3: Weighting (Cols E-F)
  sheet.getRange('E2').setValue('Weighting:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var f2 = sheet.getRange('F2');
  var weightRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['Market Cap', 'Equal Weight'], true)
    .setAllowInvalid(false)
    .build();
  f2.setDataValidation(weightRule);
  f2.setValue('Market Cap')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 4: Horizon (Cols G-H)
  sheet.getRange('G2').setValue('Horizon:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var h2 = sheet.getRange('H2');
  var horizRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['10y', '20y', '30y'], true)
    .setAllowInvalid(false)
    .build();
  h2.setDataValidation(horizRule);
  h2.setValue('30y')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Status Banner (Row 2, Cols I-N)
  sheet.getRange('I2:N2').merge()
       .setValue('Top N Portfolio Allocation Engine | Select Target Universe, Strategy, Weighting & Horizon')
       .setBackground('#2C5282')
       .setFontColor('#FFFFFF')
       .setFontSize(9)
       .setFontStyle('italic')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');

  // --- ROW 3: Execution & Tax Controls ---
  // Control 5: Rebalance Frequency (Cols A-B)
  sheet.getRange('A3').setValue('Rebalance:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var b3 = sheet.getRange('B3');
  var freqRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['Annual', 'Quarterly'], true)
    .setAllowInvalid(false)
    .build();
  b3.setDataValidation(freqRule);
  b3.setValue('Annual')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 6: Benchmark (Cols C-D)
  sheet.getRange('C3').setValue('Benchmark:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var d3 = sheet.getRange('D3');
  var benchRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['S&P 500', 'MSCI World', 'FBGRX'], true)
    .setAllowInvalid(false)
    .build();
  d3.setDataValidation(benchRule);
  d3.setValue('S&P 500')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 7: Tax Rate (Cols E-F)
  sheet.getRange('E3').setValue('Tax Rate:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var f3 = sheet.getRange('F3');
  var taxRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['0.0%', '15.0%', '20.0%', '30.0%', '37.0%'], true)
    .setAllowInvalid(false)
    .build();
  f3.setDataValidation(taxRule);
  f3.setValue(0.30)
    .setNumberFormat('0.0%')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Control 8: Seed Capital (Cols G-H)
  sheet.getRange('G3').setValue('Seed Capital:')
       .setFontWeight('bold')
       .setHorizontalAlignment('right')
       .setVerticalAlignment('middle');
  var h3 = sheet.getRange('H3');
  var seedRule = SpreadsheetApp.newDataValidation()
    .requireNumberGreaterThan(0)
    .setAllowInvalid(false)
    .setHelpText('Please enter a positive seed investment amount.')
    .build();
  h3.setDataValidation(seedRule);
  h3.setValue(BASE_INITIAL_CAPITAL)
    .setNumberFormat('$#,##0')
    .setFontWeight('bold')
    .setFontSize(11)
    .setBackground('#FEFCBF')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Helper Guidance (Row 3, Cols I-N)
  sheet.getRange('I3:N3').merge()
       .setValue('Execution & Tax Engine | Set Frequency, Reference Benchmark, Capital Gains Rate & Starting Capital')
       .setBackground('#EDF2F7')
       .setFontColor('#4A5568')
       .setFontSize(9)
       .setFontStyle('italic')
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');

  // Helper expressions for Scenario Data lookups with string-resilient tax rate formatting
  var taxExpr = 'IF(ISNUMBER($F$3), TEXT($F$3, "0.0%"), $F$3)';
  var stratKeyExpr = '$H$2 & "_" & $B$2 & "_" & $D$2 & "_" & $F$2 & "_" & $B$3 & "_" & ' + taxExpr;
  var benchKeyExpr = '$H$2 & "_" & IF($D$3="MSCI World", "All World_MSCI World", IF($D$3="FBGRX", "FBGRX_FBGRX", "S&P 500_S&P 500")) & "_" & $B$3 & "_" & ' + taxExpr;

  // 3. Dynamic KPI Summary Scorecards (Rows 5-7)
  // Card 1: Selected Strategy Final Wealth (Cols A-C)
  sheet.getRange('A5:C5').merge().setFormula('=$D$2 & " (" & $F$2 & ") Final Wealth (" & $H$2 & ")"').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A6:C6').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$L:$L, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#22543D').setNumberFormat('$#,##0.00').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A7:C7').merge().setFormula('="After all taxes (" & TEXT($H$3, "$#,##0") & " start)"').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A5:C7').setBackground('#E6FFFA').setBorder(true, true, true, true, false, false, '#B2F5EA', SpreadsheetApp.BorderStyle.SOLID);

  // Card 2: Selected Benchmark Wealth (Cols D-F)
  sheet.getRange('D5:F5').merge().setFormula('=$D$3 & " Wealth (" & $H$2 & ")"').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D6:F6').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$L:$L, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#4A5568').setNumberFormat('$#,##0.00').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D7:F7').merge().setFormula('=IF($D$3="FBGRX", "Active mutual fund", "Passive buy & hold")').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D5:F7').setBackground('#EDF2F7').setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // Card 3: Selected Strategy After-Tax CAGR (Cols G-H)
  sheet.getRange('G5:H5').merge().setFormula('="Annual Return (After-Tax)"').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('G6:H6').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#1B365D').setNumberFormat('0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('G7:H7').merge().setValue('Net after-tax annual rate (pre-liq)').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('G5:H7').setBackground('#EBF8FF').setBorder(true, true, true, true, false, false, '#BEE3F8', SpreadsheetApp.BorderStyle.SOLID);

  // Card 4: Annual Alpha vs Selected Benchmark (Cols I-K)
  sheet.getRange('I5:K5').merge().setFormula('="Annual Alpha vs " & $D$3').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('I6:K6').merge().setFormula('=(IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0) - IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0))').setFontWeight('bold').setFontSize(14).setFontColor('#22543D').setNumberFormat('+0.00%;-0.00%;0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('I7:K7').merge().setValue('Excess annual compound return').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('I5:K7').setBackground('#F0FFF4').setBorder(true, true, true, true, false, false, '#C6F6D5', SpreadsheetApp.BorderStyle.SOLID);

  // Card 5: Selected Strategy Annual Tax Drag (Cols L-N)
  sheet.getRange('L5:N5').merge().setFormula('="Annual Tax Drag (" & $D$2 & ")"').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('L6:N6').merge().setFormula('=IFERROR(INDEX(\'Scenario Data\'!$P:$P, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setFontWeight('bold').setFontSize(14).setFontColor('#9B2C2C').setNumberFormat('0.00%').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('L7:N7').merge().setValue('Annual return lost to taxes').setFontSize(9).setFontColor('#718096').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('L5:N7').setBackground('#FFF5F5').setBorder(true, true, true, true, false, false, '#FED7D7', SpreadsheetApp.BorderStyle.SOLID);

  // 4. Head-to-Head Scenario Spotlight Table (Rows 9-13)
  // Row 9: Title Banner
  sheet.getRange('A9:N9').merge()
       .setValue('HEAD-TO-HEAD PERFORMANCE & TAX SPOTLIGHT')
       .setBackground('#1B365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(11)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle');

  // Row 10: Table Header (14 columns)
  var tableHeaders = [
    'Role / Selection', 'Universe', 'Horizon', 'Frequency', 'Annual Return (Pre-Tax)', 'Annual Return (After-Tax)', 'Annual Return (Post-Liq)',
    'Total Return (Cumulative)', 'Ending Wealth', 'Total Dividends Received',
    'Max Drawdown (Worst Drop)', 'Total Taxes Paid', 'Annual Tax Drag', 'Excess vs Benchmark (Alpha)'
  ];
  sheet.getRange(10, 1, 1, tableHeaders.length).setValues([tableHeaders])
       .setBackground('#2D3748')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setFontSize(9)
       .setHorizontalAlignment('center')
       .setVerticalAlignment('middle')
       .setWrap(true);
  sheet.getRange('I10').setFormula('="Ending Wealth (" & TEXT($H$3, "$#,##0") & " Start)"');

  // Row 11: Selected Strategy Row (INDEX/MATCH from Scenario Data Cols H-Q mapped to E-N)
  sheet.getRange('A11').setFormula('="★ Strategy: " & $D$2 & " (" & $F$2 & ")"').setFontWeight('bold').setHorizontalAlignment('left').setVerticalAlignment('middle');
  sheet.getRange('B11').setFormula('=$B$2').setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C11').setFormula('=$H$2').setFontWeight('bold').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D11').setFormula('=$B$3').setFontStyle('italic').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$H:$H, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('F11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('G11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$J:$J, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('H11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$K:$K, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('I11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$L:$L, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('J11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$M:$M, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('K11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$N:$N, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('L11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$O:$O, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('M11').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$P:$P, MATCH(' + stratKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('N11').setFormula('=(F11 - F12)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('A11:N11').setBackground('#F0FFF4');

  // Row 12: Benchmark Row
  sheet.getRange('A12').setFormula('="Benchmark: " & $D$3 & " Total Return"').setFontStyle('italic').setHorizontalAlignment('left').setVerticalAlignment('middle');
  sheet.getRange('B12').setFormula('=IF($D$3="MSCI World", "All World", IF($D$3="FBGRX", "US Large Growth", "S&P 500"))').setFontStyle('italic').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('C12').setFormula('=$H$2').setFontStyle('italic').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('D12').setValue('—').setFontStyle('italic').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E12').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$H:$H, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('F12').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$I:$I, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('G12').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$J:$J, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('H12').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$K:$K, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('I12').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$L:$L, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('J12').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$M:$M, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('K12').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$N:$N, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('L12').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$O:$O, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('$#,##0.00').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('M12').setFormula('=IFERROR(INDEX(\'Scenario Data\'!$P:$P, MATCH(' + benchKeyExpr + ', \'Scenario Data\'!$A:$A, 0)), 0)').setNumberFormat('0.00%').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('N12').setValue('—').setFontStyle('italic').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('A12:N12').setBackground('#EDF2F7').setFontColor('#4A5568');

  // Row 13: Net Advantage / Delta Row
  sheet.getRange('A13').setFormula('="Net Advantage (Strategy vs " & $D$3 & ")"').setFontWeight('bold').setHorizontalAlignment('left').setVerticalAlignment('middle');
  sheet.getRange('B13:D13').setValue('—').setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E13').setFormula('=(E11 - E12)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('F13').setFormula('=(F11 - F12)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('G13').setFormula('=(G11 - G12)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('H13').setFormula('=(H11 - H12)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('I13').setFormula('=(I11 - I12)').setNumberFormat('[Color10]+$#,##0.00;[Red]-$#,##0.00;$0.00').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('J13').setFormula('=(J11 - J12)').setNumberFormat('[Color10]+$#,##0.00;[Red]-$#,##0.00;$0.00').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('K13').setFormula('=(K11 - K12)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('L13').setFormula('=(L11 - L12)').setNumberFormat('+$#,##0.00;-$#,##0.00;$0.00').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('M13').setFormula('=(M11 - M12)').setNumberFormat('+0.00%;-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('N13').setFormula('=(F11 - F12)').setNumberFormat('[Color10]+0.00%;[Red]-0.00%;0.00%').setFontWeight('bold').setHorizontalAlignment('right').setVerticalAlignment('middle');
  sheet.getRange('A13:N13').setBackground('#FEFCBF');

  // Borders for table (Rows 10-13)
  sheet.getRange(10, 1, 4, tableHeaders.length).setBorder(true, true, true, true, true, true, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // 5. Key Metrics Glossary & Explanations (Rows 15-19, directly below table)
  sheet.getRange('A15:N15').merge()
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
      ['Annual Tax Drag:', 'Annual return lost to taxes (Pre-Tax CAGR minus After-Tax CAGR).']
    ],
    [
      ['Post-Liquidation Return:', 'True net annual return assuming full final portfolio sale and tax settlement.'],
      ['Max Drawdown:', 'Worst peak-to-trough percentage decline before a new high was reached.']
    ],
    [
      ['Ending Wealth:', 'Final portfolio equity value before terminal liquidation scaled to active Seed Capital.'],
      ['Dividends & Cash Pooling:', 'Split-adjusted discrete cash collections reinvested at rebalance dates.']
    ]
  ];

  for (var eg = 0; eg < explanationsGrid.length; eg++) {
    var gr = 16 + eg;
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
  sheet.getRange(15, 1, 5, 14).setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);

  // 6. Methodology Note Callout Card (Rows 21-26)
  sheet.getRange('A21:N21').merge()
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
    var mrRow = 22 + mb;
    sheet.getRange('A' + mrRow + ':N' + mrRow).merge()
         .setValue(methodBullets[mb])
         .setFontSize(9)
         .setFontColor('#4A5568')
         .setHorizontalAlignment('left')
         .setVerticalAlignment('middle')
         .setWrap(true);
    sheet.setRowHeight(mrRow, 20);
  }

  sheet.getRange(21, 1, 6, 14).setBorder(true, true, true, true, false, false, '#CBD5E0', SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange('A22:N26').setBackground('#F7FAFC');

  // Explicit, proportional column widths (14 columns)
  var colWidths = [120, 80, 65, 75, 95, 95, 95, 95, 115, 105, 95, 95, 90, 110];
  for (var c = 0; c < colWidths.length; c++) {
    sheet.setColumnWidth(c + 1, colWidths[c]);
  }

  // Explicit row heights for single-screen view without vertical scrolling
  sheet.setRowHeight(1, 40);
  sheet.setRowHeight(2, 28);
  sheet.setRowHeight(3, 28);
  sheet.setRowHeight(4, 8);
  sheet.setRowHeight(5, 22);
  sheet.setRowHeight(6, 32);
  sheet.setRowHeight(7, 20);
  sheet.setRowHeight(8, 10);
  sheet.setRowHeight(9, 30);
  sheet.setRowHeight(10, 36);
  sheet.setRowHeight(11, 24);
  sheet.setRowHeight(12, 24);
  sheet.setRowHeight(13, 24);
  sheet.setRowHeight(14, 10);
  sheet.setRowHeight(15, 24);
  sheet.setRowHeight(20, 10);
  sheet.setRowHeight(21, 24);

  // Freeze top 3 rows (Banner & 2 Parameter Rows) for clean navigation
  sheet.setFrozenRows(3);
}

