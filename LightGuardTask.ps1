$CurrentTime = Get-Date -Format o
$ComputerName = $env:COMPUTERNAME
$CurrentUser = $env:UserName
$UserSID = (Get-WmiObject Win32_UserAccount | Where-Object { $_.Name -eq $CurrentUser }).SID
$AuthorInfo = "$ComputerName\$CurrentUser"

$InstallPath = "$env:USERPROFILE\AppData\Local\LightGuard"

$TaskXML = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>$CurrentTime</Date>
    <Author>$AuthorInfo</Author>
    <Description>When system wakes up, LightGuard runs.</Description>
    <URI>\LightGuard\LightGuardWakeUp</URI>
  </RegistrationInfo>
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription><![CDATA[
          <QueryList>
            <Query Id="0" Path="System">
              <Select Path="System">
                  *[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and (EventID=507)]]
              </Select>
            </Query>
          </QueryList>
      ]]></Subscription>
    </EventTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$UserSID</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>StopExisting</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>true</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT72H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>"$InstallPath\LightGuardWake.bat"</Command>
    </Exec>
  </Actions>
</Task>
"@

$XmlPath = "$InstallPath\LightGuardWakeUp.xml"
$TaskXML | Set-Content -Path $XmlPath -Encoding utf8

Write-Output "XML file created: $XmlPath"

Register-ScheduledTask -TaskName "LightGuardWakeUp" -TaskPath "\LightGuard" -Xml (Get-Content -Path $XmlPath -Raw)

Write-Output "The task successfully added!"