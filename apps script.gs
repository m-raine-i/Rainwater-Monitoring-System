function doGet(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Sheet1");
  var timestamp = e.parameter.time;
  var rain = e.parameter.value;

  if (timestamp && rain) {
    sheet.appendRow([timestamp, rain]);
    return ContentService.createTextOutput("Success");
  } else {
    return ContentService.createTextOutput("Missing parameters");
  }
}
