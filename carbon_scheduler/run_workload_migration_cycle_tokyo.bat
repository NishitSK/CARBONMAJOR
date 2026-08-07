@echo off
cd /d "C:\Users\Acer\Desktop\Newfolder\CARBON_MAJOR\carbon_scheduler"
python aws\real_workload_migration.py --scenario tokyo --initial-region "ap-northeast-1 (Tokyo)" >> data\workload_migration_output_tokyo.log 2>&1
