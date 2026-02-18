#!/usr/bin/env python3
"""Apply Fresh Onboarding filter logic changes to app_mysql.py"""
import glob
import os

# Find the file using glob to handle the Unicode apostrophe
pattern = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_mysql.py")
if not os.path.exists(pattern):
    # Fallback to glob
    pattern2 = os.path.expanduser("~/Documents/Documents - Aditya*MacBook Air/finaggonboaring dashboard/app_mysql.py")
    matches = glob.glob(pattern2)
    if not matches:
        print("ERROR: Could not find app_mysql.py")
        exit(1)
    filepath = matches[0]
else:
    filepath = pattern

print(f"Found file: {filepath}")

with open(filepath, 'r') as f:
    content = f.read()

changes_made = 0

# ============================================================
# CHANGE 1: Dashboard counting logic (lines 377-386)
# ============================================================
old_counting = """            # Fresh Onboarding: Parent LOS created today
            today_str = date.today().strftime('%Y-%m-%d')
            los_created_date = row.get('LOS_Created_Date')
            if isinstance(los_created_date, date):
                los_created_date_str = los_created_date.strftime('%Y-%m-%d')
            else:
                los_created_date_str = str(los_created_date)

            if rel == 'PARENT' and los_created_date_str == today_str:
                unique_pans['fresh_onboarding'].add(pan)"""

new_counting = """            # Fresh Onboarding: Both LOS_Created_Date and Invite_Date must be within date range
            start_date = data['start_date']
            end_date = data['end_date']
            los_created_date = row.get('LOS_Created_Date')
            invite_date_val = row.get('Final_Invite_Date')
            if isinstance(los_created_date, date):
                los_created_date_str = los_created_date.strftime('%Y-%m-%d')
            else:
                los_created_date_str = str(los_created_date) if los_created_date else None
            if isinstance(invite_date_val, date):
                invite_date_str = invite_date_val.strftime('%Y-%m-%d')
            else:
                invite_date_str = str(invite_date_val) if invite_date_val else None

            if (los_created_date_str and invite_date_str
                    and start_date <= los_created_date_str <= end_date
                    and start_date <= invite_date_str <= end_date):
                unique_pans['fresh_onboarding'].add(pan)"""

if old_counting in content:
    content = content.replace(old_counting, new_counting)
    print("CHANGE 1 applied: Dashboard counting logic updated")
    changes_made += 1
else:
    print("WARNING: Could not find CHANGE 1 target text")
    lines = content.split('\n')
    print("Lines 375-390:")
    for i in range(374, min(390, len(lines))):
        print(f"  {i+1}: {lines[i]}")

# ============================================================
# CHANGE 2: Popup filter logic (lines 432-436)
# ============================================================
old_popup = """            elif m_type == 'fresh_onboarding':
                today_str = date.today().strftime('%Y-%m-%d')
                los_created_date = r.get('LOS_Created_Date')
                if isinstance(los_created_date, (date, datetime)):
                    match = (rel == 'PARENT' and los_created_date.strftime('%Y-%m-%d') == today_str)"""

new_popup = """            elif m_type == 'fresh_onboarding':
                start_date = data['start_date']
                end_date = data['end_date']
                los_created_date = r.get('LOS_Created_Date')
                invite_date_val = r.get('Final_Invite_Date')
                los_str = los_created_date.strftime('%Y-%m-%d') if isinstance(los_created_date, (date, datetime)) else None
                inv_str = invite_date_val.strftime('%Y-%m-%d') if isinstance(invite_date_val, (date, datetime)) else None
                match = (los_str is not None and inv_str is not None
                         and start_date <= los_str <= end_date
                         and start_date <= inv_str <= end_date)"""

if old_popup in content:
    content = content.replace(old_popup, new_popup)
    print("CHANGE 2 applied: Popup filter logic updated")
    changes_made += 1
else:
    print("WARNING: Could not find CHANGE 2 target text")
    lines = content.split('\n')
    print("Lines 430-440:")
    for i in range(429, min(440, len(lines))):
        print(f"  {i+1}: {lines[i]}")

if changes_made > 0:
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"\nDone! {changes_made} change(s) saved to {filepath}")
else:
    print("\nNo changes were made.")
