# Implementation Plan - East Zone Validation Model Setup & UI Display

This plan sets up a fresh, extensible "East Zone Model" infrastructure to support custom documents, validation prompts, and JSON structures for the East Zone. It also introduces a dynamic "Active Zone" display indicator in the automation dashboard user interface.

## User Review Required

> [!IMPORTANT]
> - **East Zone Model Architecture**: We will create a structured namespace/class `EastZoneModel` in [automate_login.py](file:///c:/Users/admin/Desktop/robbinmahindra/automate_login.py) containing placeholders for East Zone-specific ChatGPT prompts, classification rules, and validation checks.
> - **Zero Side-effects**: To ensure no current validation flows are affected, the East Zone validation pipeline will fall back to common validation checks for any documents/rules that are not yet custom-defined.
> - **Dynamic UI Display**: We will add a color-coded status label to the application header showing the active zone (`COMMON`, `EAST`, `SOUTH`, etc.) as detected by the backend automation script.

---

## Proposed Changes

### 1. Backend Automation Logic

#### [MODIFY] [automate_login.py](file:///c:/Users/admin/Desktop/robbinmahindra/automate_login.py)

- **Define `EastZoneModel` [NEW]**:
  Add a helper class containing stubbed out entrypoints for East Zone-specific logic:
  - `get_openai_prompt(filename_hint)`: Custom OpenAI prompt for ChatGPT Vision API to read and format East Zone documents.
  - `classify_and_extract(file_path, text, ...)`: Custom classification of files into East Zone types.
  - `verify_documents(...)`: Custom validation script for comparing ChatGPT response fields against the dashboard metadata.
  
- **Integrate `EastZoneModel` hooks**:
  - In `extract_details_via_openai(...)`: If `CURRENT_ZONE` is `"EAST"`, use `EastZoneModel.get_openai_prompt`.
  - In `classify_and_extract(...)`: If `CURRENT_ZONE` is `"EAST"`, allow delegating/falling back to `EastZoneModel.classify_and_extract`.
  - In `verify_documents(...)`: If `CURRENT_ZONE` is `"EAST"`, delegate document verification to `EastZoneModel.verify_documents`.

---

### 2. Frontend User Interface

#### [MODIFY] [app_ui.py](file:///c:/Users/admin/Desktop/robbinmahindra/app_ui.py)

- **Add Active Zone Label**:
  In `create_layout`, pack a new label next to the main window title to visually display the active running zone model.
  
- **Poll Active Zone**:
  In `poll_queues`, dynamically check `automate_login.CURRENT_ZONE` and update the label text and foreground color (e.g. green for `EAST`, blue for other active zones, amber for common/default).

---

## Verification Plan

### Automated Verification
- Compile and syntax-check the modified python files:
  ```powershell
  python -m py_compile automate_login.py app_ui.py
  ```
- Run local unit tests (if any) to ensure no regressions.

### Manual Verification
- Launch the dashboard using:
  ```powershell
  python app_ui.py
  ```
- Verify that `"Active Zone: COMMON"` is displayed in the header on startup.
- Run a test claim or mock the active zone to `"EAST"` to confirm the UI updates its color and label text to `"Active Zone: EAST"` dynamically, and the console shows the custom `"[East Zone Model]"` validation logs.
