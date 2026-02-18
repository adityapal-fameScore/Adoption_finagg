# Walkthrough - Running Finagg Onboarding Dashboard

I have successfully set up and started the Finagg Onboarding dashboard. Below is a summary of the accomplishments and verification results.

## Changes Made

### Environment Setup
- **Installed Dependencies**: Installed `Flask`, `flask-cors`, and `mysql-connector-python`.
- **Started Application**: Launched the Flask application in the background on port `8087`.
- **UI Refinements**:
    - **Stabilized Table**: Optimized layout to prevent column shrinking during filtering.
    - **Fixed Dropdowns**: Implemented fixed positioning to prevent clipping by the table container.
- **WhatsApp Logic Refinement**: Refined logic using `cbs_prodn` session data. (Completed)
- **Anchor Name Extraction**: Logic implemented to extract anchor codes. (Completed)
- **Filtered CSV Export**: 
    - **Logic**: Updated the export function to only include rows currently visible in the table.
    - **State Management**: Introduced `displayedData` in JS to synchronize the export with active filters.
- **Application Rename**: The main file was renamed to `Adoption_Dashboard.py`. (Completed)
- **Table Sorting (Asc/Desc)**:
    - **UI**: Added clickable table headers with arrows (↑ ↓) to indicate sort direction.
    - **Logic**: Implemented a `sortTable` function in JS that handles alphabetical, numeric, and date sorting.
    - **Integration**: Sorting works seamlessly with the existing multi-column filters.
- **Render Deployment Preparation**: Configuration files created. (Completed)
- **Deployment Alternatives**: Researched and documented Railway vs. VPS.

## Deployment Alternatives (Non-Render)

### Option 1: Railway.app (PaaS)
Similar to Render but usually more robust with Docker.
1. Connect GitHub.
2. Select **Docker** as the builder.
3. Railway will use the `Dockerfile` I created.

### Option 2: DigitalOcean Droplet / AWS EC2 (VPS) - *Recommended*
1. **Create a Linux VM** (Ubuntu 22.04).
2. **Install OpenVPN**: `sudo apt install openvpn`.
3. **Run VPN**: `sudo openvpn --config adityagcp.ovpn --daemon`.
4. **Install Python/Flask** and run: `python3 Adoption_Dashboard.py`.

### Deployment Option 3: PythonAnywhere
> [!CAUTION]
> **Warning**: Database connection (172.21.2.7) will **fail** on PythonAnywhere because it does not support OpenVPN. These steps are provided only for setting up the web interface.

1. **Upload Files**: Log in and upload `Adoption_Dashboard.py`, `requirements.txt`, and `adityagcp.ovpn`.
2. **Setup VirtualEnv**:
   - Open a Bash console.
   - Run: `mkvirtualenv --python=/usr/bin/python3.10 dashboard-env`
   - Run: `pip install -r requirements.txt`
3. **Configure Web Tab**:
   - Go to the **Web** tab and click **Add a new web app**.
   - Choose **Manual configuration** -> **Python 3.10**.
   - Set **Source code** path: `/home/yourusername/`
   - Set **Virtualenv** path: `/home/yourusername/.virtualenvs/dashboard-env`
4. **Edit WSGI Configuration**:
   - In the Web tab, click the link to your WSGI configuration file.
   - Replace the content with:
     ```python
     import sys
     path = '/home/yourusername/'
     if path not in sys.path:
         sys.path.append(path)
     from Adoption_Dashboard import app as application
     ```
5. **Reload**: Click the **Reload** button at the top of the Web tab.

## Final Verification Results
- **Local Dashboard**: [http://localhost:8087](http://localhost:8087) - **Functional** (with VPN active).
- **GitHub Repo**: [Adoption_finagg](https://github.com/adityapal-fameScore/Adoption_finagg.git) - **Pushed**.
- **User Interface**: Columns stabilized, dropdowns fixed, CSV export filtered.
- **Sourcing Logic**: WhatsApp sourcing now uses `cbs_prodn` session data.
- **Anchor Name**: Automatically parsed and displayed.

## Verification Results

### Success Confirmation
The application is active and successfully communicating with the database.

- **Dashboard UI**: Responding at `http://localhost:8087` with a `200 OK` status.
- **API Connectivity**: The `/api/dashboard` endpoint was tested with a sample date range and returned valid metrics data from the MySQL database.

### API Response Preview
```json
{
  "metrics": {
    "total": {
      "ai_pd": 2,
      "ai_pd_answered": 0,
      "anchor": 0,
      "fame_score": 0,
      "fame_to_finagg": 2,
      "fresh_onboarding": 1,
      "invite_only": 0,
      "retail": 0,
      "sme": 0,
      "total_onboarded": 2,
      "whatsapp": 0
    }
  }
}
```

## How to Access
The dashboard is currently running in the background. You can access it at:
[http://localhost:8087](http://localhost:8087)
