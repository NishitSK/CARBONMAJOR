@echo off
cd /d "C:\Users\Acer\Desktop\Newfolder\CARBON_MAJOR\carbon_scheduler"
python aws\real_workload_migration.py --scenario mumbai --initial-region "ap-south-1 (Mumbai)" >> data\workload_migration_output_mumbai.log 2>&1
