schtasks /delete /tn "CarbonWorkloadMigrationCycle_Mumbai" /f 2>$null

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <TimeTrigger>
      <Repetition>
        <Interval>PT1H</Interval>
        <Duration>P7D</Duration>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2026-07-07T14:40:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <StartWhenAvailable>true</StartWhenAvailable>
  </Settings>
  <Actions>
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-WindowStyle Hidden -Command &quot;cd &apos;C:\Users\Acer\Desktop\Newfolder\CARBON_MAJOR\carbon_scheduler&apos;; python aws\real_workload_migration.py --scenario mumbai --initial-region &apos;ap-south-1 (Mumbai)&apos; &gt;&gt; data\workload_migration_output_mumbai.log 2&gt;&amp;1&quot;</Arguments>
    </Exec>
  </Actions>
</Task>
"@

Register-ScheduledTask -TaskName "CarbonWorkloadMigrationCycle_Mumbai" -Xml $xml -Force

Write-Host "Workload migration task registered (Mumbai-origin scenario): runs hourly at :40 past the hour."
schtasks /query /tn "CarbonWorkloadMigrationCycle_Mumbai" /fo LIST /v | Select-String "Next Run|Status|Power|Repeat"
