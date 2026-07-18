function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  
  // If the sheet is empty, initialize headers
  if (sheet.getLastRow() === 0) {
    sheet.appendRow([
      "Row Number", "Claim Number", "Claim Date", "Area Office", 
      "Customer Name", "Dealer Name", "Dealer Branch", "Scheme", 
      "Status", "Hold Reasons / Remarks", "Processed Date", "Chassis No"
    ]);
  }
  
  try {
    var data = JSON.parse(e.postData.contents);
    
    // Get headers in first row to map dynamically
    var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    
    // Map keys to their normalized header matching
    var keyMap = {
      "row_num": ["row number", "row #", "row", "row_num", "rownum"],
      "claim_no": ["claim number", "claim no", "claim #", "claim_no", "claimno"],
      "claim_date": ["claim date", "date of claim", "claim_date", "claimdate"],
      "area_office": ["area office", "office", "area_office", "areaoffice"],
      "customer_name": ["customer name", "customer", "customer_name", "customername"],
      "dealer_name": ["dealer name", "dealer", "dealer_name", "dealername"],
      "dealer_branch": ["dealer branch", "branch", "dealer_branch", "dealerbranch"],
      "scheme": ["scheme", "scheme type", "scheme_type"],
      "status": ["status", "validation status", "state"],
      "hold_reasons": ["hold reasons / remarks", "hold reasons", "remarks", "hold_reasons", "holdreasons"],
      "date_processed": ["processed date", "date processed", "date_processed", "dateprocessed"],
      "chassis_no": ["chassis no", "chassis number", "chassis", "chassis_no", "chassisno"]
    };
    
    var newRow = [];
    for (var i = 0; i < headers.length; i++) {
      var headerVal = headers[i].toString().toLowerCase().trim();
      var cellVal = "";
      
      // Look for a key that maps to this header
      for (var key in keyMap) {
        if (keyMap[key].indexOf(headerVal) !== -1 || headerVal.indexOf(key) !== -1) {
          if (data[key] !== undefined) {
            cellVal = data[key];
          }
          break;
        }
      }
      newRow.push(cellVal);
    }
    
    // If no dynamic match, fallback to standard order
    if (newRow.filter(function(x) { return x !== ""; }).length === 0) {
      newRow = [
        data.row_num || "",
        data.claim_no || "",
        data.claim_date || "",
        data.area_office || "",
        data.customer_name || "",
        data.dealer_name || "",
        data.dealer_branch || "",
        data.scheme || "",
        data.status || "",
        data.hold_reasons || "",
        data.date_processed || "",
        data.chassis_no || ""
      ];
    }
    
    sheet.appendRow(newRow);
    
    return ContentService.createTextOutput(JSON.stringify({status: "success"}))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({status: "error", message: err.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
