@echo off
cd /d "C:\Users\Acer\Desktop\Newfolder\CARBON_MAJOR\carbon_scheduler"
python aws\run_one_cycle_cloud_vantage.py >> data\cloud_vantage_output.log 2>&1
