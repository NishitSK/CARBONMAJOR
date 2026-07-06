schtasks /delete /tn "CarbonPilotCloudVantageCycle" /f 2>$null

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
      <StartBoundary>2026-07-04T15:30:00</StartBoundary>
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
      <Arguments>-WindowStyle Hidden -Command &quot;cd &apos;C:\Users\Acer\Desktop\Newfolder\CARBON_MAJOR\carbon_scheduler&apos;; python aws\run_one_cycle_cloud_vantage.py &gt;&gt; data\cloud_vantage_output.log 2&gt;&amp;1&quot;</Arguments>
    </Exec>
  </Actions>
</Task>
"@

Register-ScheduledTask -TaskName "CarbonPilotCloudVantageCycle" -Xml $xml -Force

Write-Host "Cloud-vantage task registered: runs hourly, offset 30 min from the main laptop-vantage cycle."
schtasks /query /tn "CarbonPilotCloudVantageCycle" /fo LIST /v | Select-String "Next Run|Status|Power|Repeat"
