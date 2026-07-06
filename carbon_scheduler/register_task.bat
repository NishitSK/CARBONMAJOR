@echo off
schtasks /delete /tn "CarbonPilotCycle" /f 2>nul

powershell -Command "& { $xml = @'
<?xml version=\"1.0\" encoding=\"UTF-16\"?>
<Task version=\"1.2\" xmlns=\"http://schemas.microsoft.com/windows/2004/02/mit/task\">
  <Triggers>
    <TimeTrigger>
      <Repetition>
        <Interval>PT1H</Interval>
        <Duration>P7D</Duration>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2026-07-02T21:00:00</StartBoundary>
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
      <Command>C:\Users\Acer\Desktop\Newfolder\CARBON_MAJOR\carbon_scheduler\run_cycle.bat</Command>
    </Exec>
  </Actions>
</Task>
'@; Register-ScheduledTask -TaskName 'CarbonPilotCycle' -Xml $xml -Force }"

powercfg /setdcvalueindex SCHEME_CURRENT 4f971e89-eebd-4455-a8de-9e59040e7347 5ca83367-6e45-459f-a27b-476b1d01c936 0
powercfg /setacvalueindex SCHEME_CURRENT 4f971e89-eebd-4455-a8de-9e59040e7347 5ca83367-6e45-459f-a27b-476b1d01c936 0
powercfg /apply SCHEME_CURRENT

echo.
schtasks /query /tn "CarbonPilotCycle" /fo LIST /v | findstr /i "Next Run Status Power Repeat"
pause
