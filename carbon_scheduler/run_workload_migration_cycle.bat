@echo off
cd /d "C:\Users\Acer\Desktop\Newfolder\CARBON_MAJOR\carbon_scheduler"
python aws\real_workload_migration.py >> data\workload_migration_output.log 2>&1
